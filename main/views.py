import logging
from datetime import timedelta, datetime
from operator import attrgetter

import pandas as pd
import plotly.express as px
from django.core.cache import cache
from django.db.models import Q, Count, F
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.timezone import now, make_aware
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.generic import ListView, TemplateView, DetailView

from bgg.settings import CACHE_DURATION
from main.models import Game, Player, Review, Day

logger = logging.getLogger(__name__)


def home_view(request):
    ctx = cache.get('home_view')
    if not ctx:
        upcoming = Game.objects.filter(
            Q(recs_cnt__isnull=False) &
            Q(hotness__isnull=False)
        ).annotate(score=F('recs_cnt') / (F('reviews_cnt') + F('hotness'))).order_by(
            '-score').all()[:5]
        ctx = {
            'nav': 'home',
            'game_cnt': Game.objects.count(),
            'player_cnt': Player.objects.count(),
            'reviews_cnt': Review.objects.count(),
            'hotness': Game.objects.order_by('-hotness')[:10],
            'upcoming': upcoming,
        }
        cache.set('home_view', ctx)
    return render(request, 'main/home.html', ctx)


def about_view(request):
    ctx = cache.get('about_view')
    if not ctx:
        sept13 = make_aware(datetime(2021, 9, 13))
        # player updated
        player_cnt = Player.objects.count()
        last_updated_rec = Player.objects.filter(
            Q(reviews_scr__gte=1) &
            Q(reviews_scr__lte=10) &
            Q(reviews_cnt__gte=3) &
            Q(updated_at__gt=sept13)
        ).order_by('rec_at').first()
        player_turnover = (now() - last_updated_rec.rec_at).days
        # game added
        one_month = now() - timedelta(days=30)
        first_game = Game.objects.filter(
            created_at__gte=one_month).order_by('created_at').first()
        total_games = Game.objects.filter(
            created_at__gte=one_month).count()
        game_days = (now() - first_game.created_at).days
        game_added = total_games // game_days
        ctx = {
            'player_turnover': player_turnover,
            'game_added': game_added,
        }
        cache.set('about_view', ctx)
    return render(request, 'main/about.html', context=ctx)


class ViewError(Exception):
    """Bad view setup"""


@method_decorator(cache_page(CACHE_DURATION), name='dispatch')
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

        # prev and next
        ctx['prev'] = Game.objects.filter(
            rating__gt=self.object.rating).order_by('rating', '-rank').first()
        ctx['next'] = Game.objects.filter(
            rating__lt=self.object.rating).order_by('-rating', 'rank').first()

        # graph histogram
        histogram = self.object.reviews.values('rating')
        df = pd.DataFrame(list(histogram))
        fig = px.box(df, y='rating')
        fig.update_yaxes(tick0=1, dtick=1)
        ctx['rating_graph'] = fig.to_html(full_html=False)

        # graph daily
        day_data = self.object.reviews.annotate(
            month=TruncMonth('reviewed_at')).order_by('month').values('month').annotate(
            cnt=Count('month')).values('month', 'cnt')
        if day_data:
            day_df = pd.DataFrame([
                {'Month': d['month'], 'Ratings': d['cnt']}
                for d in day_data])
            day_fig = px.bar(day_df, x='Month', y='Ratings', title='Ratings per month')
            ctx['day_graph'] = day_fig.to_html(full_html=False)

        return ctx


class PlayerListView(OrderingListView, SearchListView, CachedDispatch):
    model = Player
    paginate_by = 100
    ordering = '-reviews_scr'
    search_by = 'nick'
    queryset = Player.objects.filter(
        Q(reviews_scr__gt=1) &
        Q(reviews_scr__lt=10) &
        Q(reviews_cnt__gte=3) &
        Q(updated_at__gt=make_aware(datetime(2021, 9, 13))))


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
        fig = px.scatter(df, x="Expected", y="Actual", hover_name='Name')
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
            df_rating, x='rating', y='cnt', histfunc='sum', range_x=(0, 10),
            labels={'rating': 'Rating value', 'cnt': 'count'},
            title='Histogram of ratings')
        fig_rating.update_traces(nbinsx=20, autobinx=False)
        data['graph_rating'] = fig_rating.to_html(full_html=False)

        # graph of daily ratings
        days = Day.objects.order_by('-day').all()[:30]
        data_day = [
            {'Date': d.day, 'Ratings': d.reviews_cnt}
            for d in days]
        df = pd.DataFrame(data_day)
        fig_day = px.bar(
            df, x="Date", y="Ratings", labels={'Ratings': '# of ratings'},
            title='Ratings past ~month')
        data['graph_day'] = fig_day.to_html(full_html=False)

        return data
