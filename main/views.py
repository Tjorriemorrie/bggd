import logging
from operator import attrgetter

import pandas as pd
import plotly.express as px
from django.core.cache import cache
from django.db.models import Q, Count
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.generic import ListView, TemplateView, DetailView

from main.models import Game, Player, Review

logger = logging.getLogger(__name__)


def home_view(request):
    ctx = cache.get('home_view')
    if not ctx:
        ctx = {
            'nav': 'home',
            'game_cnt': Game.objects.count(),
            'player_cnt': Player.objects.count(),
            'review_cnt': Review.objects.count(),
        }
        cache.set('home_view', ctx)
    return render(request, 'main/home.html', ctx)


def about_view(request):
    return render(request, 'main/about.html')


class ViewError(Exception):
    """Bad view setup"""


# @method_decorator(cache_page(60 * 60 * 24), name='dispatch')
class CachedDispatch(View):
    pass


class OrderingListView(ListView):
    ordering = None

    def get_ordering(self):
        if not self.ordering:
            raise ViewError('Missing ordering on view')
        return self.request.GET.get('o', self.ordering)

    def get_context_data(self, *, object_list=None, **kwargs):
        ctx = super().get_context_data(object_list=object_list, **kwargs)
        ctx['ordering'] = self.get_ordering()
        return ctx


class SearchListView(ListView):
    search_by = None

    def get_context_data(self, *, object_list=None, **kwargs):
        ctx = super().get_context_data(object_list=object_list, **kwargs)
        ctx['s'] = self.request.GET.get('s')
        return ctx

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get('s')
        if not self.search_by:
            raise ViewError('Missing search_by on view.')
        if search:
            q = None
            for val in search.split():
                params = {f'{self.search_by}__icontains': val}
                if not q:
                    q = Q(**params)
                else:
                    q.add(Q(**params), Q.OR)
            queryset = queryset.filter(q)
        return queryset


class GameListView(OrderingListView, SearchListView, CachedDispatch):
    model = Game
    paginate_by = 50
    ordering = '-rating'
    search_by = 'name'
    queryset = Game.objects.filter(rating__isnull=False)


class GameDetailView(DetailView):
    model = Game
    context_object_name = 'game'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['prev'] = Game.objects.filter(
            rating__gt=self.object.rating).order_by('rating', '-rank').first()
        ctx['next'] = Game.objects.filter(
            rating__lt=self.object.rating).order_by('-rating', 'rank').first()
        histogram = self.object.reviews.values('rating')
        df = pd.DataFrame(list(histogram))
        fig = px.box(df, y='rating')
        fig.update_yaxes(tick0=1, dtick=1)
        # fig = px.histogram(df, x='rating', range_x=(1, 10))
        ctx['rating_graph'] = fig.to_html(full_html=False)
        return ctx


class PlayerListView(OrderingListView, SearchListView, CachedDispatch):
    model = Player
    paginate_by = 100
    ordering = '-reviews_scr'
    search_by = 'nick'
    queryset = Player.objects.filter(reviews_scr__isnull=False)


class PlayerDetailView(DetailView):
    model = Player
    context_object_name = 'player'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)

        # graph
        fig_data = [
            {'Actual': r.rating, 'Expected': r.predicted, 'Name': r.game.name}
            for r in self.object.reviews.all()
            if r.rating and r.predicted]
        min_est = min([f['Expected'] for f in fig_data])
        max_est = max([f['Expected'] for f in fig_data])
        df = pd.DataFrame(fig_data)
        fig = px.scatter(
            df, x="Expected", y="Actual", hover_name='Name',
            marginal_y="box")
        fig.add_shape(type="line", x0=min_est, y0=min_est, x1=max_est, y1=max_est)
        fig.update_yaxes(dtick=1)
        fig.update_xaxes(dtick=1)
        data['graph'] = fig.to_html(full_html=False)

        # reviews sorted
        if self.object.reviews.count():
            reviews = list(self.object.reviews.all())
            reviews.sort(key=attrgetter('diff'), reverse=True)
            data['reviews'] = reviews

        return data


class ReviewView(TemplateView, CachedDispatch):
    template_name = 'main/reviews.html'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)

        # rating histogram graph
        histogram = Review.objects.values('rating').annotate(
            cnt=Count('rating'))
        df_rating = pd.DataFrame(list(histogram))
        fig_rating = px.histogram(
            df_rating, x='rating', y='cnt', histfunc='sum', range_x=(0, 10))
        fig_rating.update_traces(nbinsx=20, autobinx=False)
        data['graph_rating'] = fig_rating.to_html(full_html=False)

        # ratings per day graph
        # per_day = Review.objects \
        #     .annotate(day=TruncDay('reviewed_at')).values('day') \
        #     .annotate(cnt=Count('id')) \
        #     .values('day', 'cnt')
        # df_day = pd.DataFrame(list(per_day))
        # df_day['day'] = pd.to_datetime(df_day['day'], infer_datetime_format=True)
        # fig_day = px.histogram(
        #     df_day, x='day', y='cnt', histfunc='sum')
        # fig_day.update_traces(xbins_size="M1")
        # data['graph_day'] = fig_day.to_html(full_html=False)

        return data
