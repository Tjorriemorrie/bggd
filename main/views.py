import logging
from collections import Counter
from datetime import timedelta, datetime
from itertools import combinations
from operator import attrgetter

import pandas as pd
import plotly.express as px
from django.db.models import Q, Count, F, Sum, Avg
from django.db.models.functions import TruncMonth, Least
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.timezone import now, make_aware
from django.views.decorators.cache import cache_page
from django.views.generic import ListView, TemplateView, DetailView
from pytube import Search

from bgg.settings import CACHE_DURATION
from main.constants import START_GAME_OF_THE, WEIGHTS, PLAYERS_SIZES, \
    WEIGHTS_CUTOFF, SHOP_RARU, SHOP_MEEPS_AND_VEEPS, SHOP_TIMELESS, \
    SHOP_NAMES, REC_MIN_CUTOFF, REC_MAX_CUTOFF, IGNORE_FAMILIES, SOME_YEARS_AGO
from main.models import Game, Player, Review, Day, Award, \
    AWARD_GAME_OF_THE_YEAR, \
    AWARD_GAME_OF_THE_MONTH, ShopGame, Shop

logger = logging.getLogger(__name__)

OCT1 = make_aware(datetime(2021, 10, 1))


@method_decorator(cache_page(CACHE_DURATION), name='get')
class CachedTemplateViewGet(TemplateView):
    pass


class HomeView(CachedTemplateViewGet):
    template_name = 'main/home.html'

    def get_context_data(self, **kwargs):
        days_90 = now() - timedelta(days=90)
        latest = Game.objects.filter(
            created_at__gt=days_90).order_by('-hotness').all()[:5]
        upcoming = Game.objects.filter(
            Q(recs_cnt__gt=0) &
            Q(hotness__gt=0)
        ).annotate(score=100 * F('recs_cnt') / F('reviews_cnt')).order_by(
            '-score').all()[:10]
        hotness = Game.objects.order_by('-hotness')[:10]
        ctx = {
            'nav': 'home',
            'game_cnt': Game.objects.count(),
            'player_cnt': Player.objects.count(),
            'reviews_cnt': Review.objects.count(),
            'hotness': hotness,
            'upcoming': upcoming,
            'latest': latest,
        }
        return ctx


class GotView(CachedTemplateViewGet):
    template_name = 'main/got.html'

    def get_context_data(self, **kwargs):
        award_groups = {}
        to = now().year + 1
        for year in reversed(range(START_GAME_OF_THE.year, to)):
            half_year = make_aware(datetime(year, 7, 1))
            award_groups[year] = {
                'year': Award.objects.filter(
                    Q(type=AWARD_GAME_OF_THE_YEAR)
                    & Q(awarded_at__year=year)
                ).first(),
                'top': Award.objects.filter(
                    Q(type=AWARD_GAME_OF_THE_MONTH)
                    & Q(awarded_at__year=year)
                    & Q(awarded_at__lt=half_year)
                ).order_by('awarded_at').all(),
                'bottom': Award.objects.filter(
                    Q(type=AWARD_GAME_OF_THE_MONTH)
                    & Q(awarded_at__year=year)
                    & Q(awarded_at__gte=half_year)
                ).order_by('awarded_at').all(),
            }
        ctx = {
            'start_at': START_GAME_OF_THE,
            'award_groups': award_groups,
        }
        return ctx


class AboutView(CachedTemplateViewGet):
    template_name = 'main/about.html'

    def get_context_data(self, **kwargs):
        # player updated
        oldest_player = Player.objects.annotate(
            oldest_date=Least('scraped_at', 'rec_at')
        ).filter(oldest_date__isnull=False).order_by('oldest_date').first()
        player_turnover = (now() - oldest_player.oldest_date).days

        # game added
        one_month = now() - timedelta(days=30)
        first_game = Game.objects.filter(
            created_at__gte=one_month).order_by('created_at').first()
        total_games = Game.objects.filter(
            created_at__gte=one_month).count()
        game_days = (now() - first_game.created_at).days
        game_added = total_games // game_days

        ctx = {
            'game_added': game_added,
            'player_turnover': player_turnover,
            'min_used': REC_MIN_CUTOFF,
            'max_used': REC_MAX_CUTOFF,
        }
        return ctx


class ViewError(Exception):
    """Bad view setup"""


@method_decorator(cache_page(CACHE_DURATION), name='get')
class CachedListViewGet(ListView):
    pass


@method_decorator(cache_page(CACHE_DURATION), name='get')
class CachedDetailViewGet(DetailView):
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


class GameListView(OrderingListView, SearchListView, CachedListViewGet):
    model = Game
    paginate_by = 100
    search_by = 'name'
    queryset = Game.objects.exclude(hotness__isnull=True)
    ordering = '-hotness'

    def get_queryset(self):
        queryset = super().get_queryset()
        availability = int(self.request.GET.get('a', 1))
        if not self.request.GET.get('s') and availability:
            queryset = queryset.filter(shop_available=True)
        return queryset

    def get_context_data(self, *, object_list=None, **kwargs):
        ctx = super().get_context_data(object_list=object_list, **kwargs)
        ctx['weights_percentiles'] = WEIGHTS_CUTOFF
        # show only available
        ctx['available'] = 0 if self.request.GET.get('s') else int(self.request.GET.get('a', 1))
        return ctx


class GameDetailView(CachedDetailViewGet):
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

        yt_search = Search(f'board game review {self.object.name} {self.object.year}')
        ctx['yt_results'] = [{
            'embed_url': yt.embed_url,
            'title': yt.title,
            'author': yt.author,
        } for yt in yt_search.results][:6]

        return ctx


class PlayerListView(OrderingListView, SearchListView, CachedListViewGet):
    model = Player
    paginate_by = 100
    ordering = '-last_review_at'
    search_by = 'nick'
    queryset = Player.objects.filter(
        reviews_cnt__gte=3,
        last_review_at__year__gt=SOME_YEARS_AGO)

    def get_context_data(self, *args, object_list=None, **kwargs):
        ctx = super().get_context_data(*args, object_list=object_list, **kwargs)

        # add graph for listing only (not on search)
        # if not ctx['s']:
        #     today = now()
        #     days = Review.objects.values('player').annotate(
        #         last_day=Max('reviewed_at')
        #     ).order_by('player').values_list('last_day', flat=True)

        ctx['some_years_ago'] = SOME_YEARS_AGO
        return ctx


class PlayerDetailView(DetailView):
    model = Player
    context_object_name = 'player'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)

        data['weights'] = WEIGHTS
        data['player_sizes'] = PLAYERS_SIZES

        # graph
        fig_data = [
            {'Actual': r.rating, 'Expected': r.predicted, 'Name': r.game.name}
            for r in self.object.reviews.all()
            if r.rating and r.predicted]
        if fig_data:
            min_est = min([f['Expected'] for f in fig_data])
            max_est = max([f['Expected'] for f in fig_data])
            df = pd.DataFrame(fig_data)
            fig = px.scatter(df, x="Expected", y="Actual", hover_name='Name', title='Actual vs expected rating')
            fig.add_shape(type="line", x0=min_est, y0=min_est, x1=max_est, y1=max_est)
            fig.update_yaxes(dtick=1)
            fig.update_xaxes(dtick=1)
            data['graph'] = fig.to_html(full_html=False)

        # reviews sorted
        if self.object.reviews.count():
            reviews = list(self.object.reviews.filter(
                predicted__isnull=False,
            ).all())
            reviews.sort(key=attrgetter('predicted'), reverse=True)
            reviews.sort(key=attrgetter('rating'), reverse=True)
            data['reviews'] = reviews

            # player count
            p_data = {
                'Very Light': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                'Light': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                'Medium': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                'Heavy': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                'Very Heavy': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            }
            for review in reviews:
                if review.game.best_min_players is None or review.game.best_max_players is None:
                    continue
                for p in range(review.game.best_min_players, review.game.best_max_players + 1):
                    if p in p_data[review.game.weight_tag]:
                        p_data[review.game.weight_tag][p] += 1
            # layout = {'xaxis': {'ticks': [int(x) for x in df['player_count']]}}
            # fig = px.bar(df, x='player_count', y='count', title='Number of games per best player count')
            h_data = [list(p.values()) for p in p_data.values()]
            fig = px.imshow(
                h_data, x=[1, 2, 3, 4, 5], y=['very light', 'light', 'medium', 'heavy', 'very heavy'],
                labels={'x': 'Player count', 'y': 'Complexity'}, title='Heatmap of player games')
            data['heat'] = fig.to_html(full_html=False)

        return data


def player_predict_view(request, pk):
    """
    Prevent spam by checking requested_at is empty.
    """
    player = Player.objects.get(pk=pk)
    if not player.redo_requested_at:
        player.redo_requested_at = now()
        player.redo_started_at = None
        player.save()
    return redirect(player)


class ReviewView(CachedTemplateViewGet):
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

        reviews_cnts = Player.objects.filter(
            reviews_cnt__gte=3,
            reviews_cnt__lte=100
        ).values_list('reviews_cnt', flat=True)
        cntr = Counter(reviews_cnts)
        df = pd.DataFrame(cntr.items())
        fig = px.histogram(
            x=df[0], y=df[1], nbins=100,
            labels={'x': 'number of reviews', 'y': 'players'})
        # fig.update_yaxes(tick0=1, dtick=1)
        data['graph_reviews_cnt'] = fig.to_html(full_html=False)

        return data


class ShopView(CachedTemplateViewGet):
    template_name = 'main/shop.html'

    def get_context_data(self, **kwargs):
        games = Game.objects.filter(
            shop_available=True,
            shop_saving__gte=0
        ).order_by('-shop_saving', '-hotness').all()[:20]

        # shop sizes
        df_data = []
        for shop_name in SHOP_NAMES:
            shop = Shop.objects.get(name=shop_name)
            for inv in ['MIA', 'Out of Stock', 'In Stock']:
                qs = ShopGame.objects.filter(shop=shop)
                if inv == 'MIA':
                    qs = qs.filter(mia=True)
                elif inv == 'In Stock':
                    qs = qs.filter(mia=False, url__isnull=False, current_available=True)
                    df_data.append({'shop': shop_name, 'in stock': qs.count()})
                elif inv == 'Out of Stock':
                    qs = qs.filter(mia=False, url__isnull=False, current_available=False)
                # df_data.append({'shop': shop_name, 'inventory': inv, 'count': qs.count()})
        df = pd.DataFrame(df_data)
        # fig_shop_size = px.bar(
        #     df, x='shop', y='count', color='inventory',
        #     title='Shop size', color_discrete_sequence=['#bfbfbf', '#f72572', '#3af725'])
        fig_shop_size = px.bar(
            df, x='shop', y='in stock',
            title='Shop size')

        # shop price heatmap
        heat_data = {}
        combs = combinations(SHOP_NAMES, 2)
        for name1, name2 in combs:
            if name1 not in heat_data:
                heat_data[name1] = {n: 0 for n in SHOP_NAMES}
            if name2 not in heat_data:
                heat_data[name2] = {n: 0 for n in SHOP_NAMES}
            game_ids = Game.objects.filter(
                shopgames__shop__name__in=[name1, name2]
            ).exclude(
                Q(shopgames__current_available=False) |
                Q(shopgames__mia=True)
            ).values_list('id', flat=True)
            qs1 = ShopGame.objects.filter(
                shop__name=name1, game__id__in=game_ids
            ).all().aggregate(Avg('current_price'))
            qs2 = ShopGame.objects.filter(
                shop__name=name2, game__id__in=game_ids
            ).all().aggregate(Avg('current_price'))
            v = qs2['current_price__avg'] - qs1['current_price__avg']
            heat_data[name1][name2] = v
            heat_data[name2][name1] = -v
        heat_raw = [list(p.values()) for p in heat_data.values()]
        fig_shop_price = px.imshow(
            heat_raw, x=SHOP_NAMES, y=SHOP_NAMES,
            title='Avg price war of same games in stock<br><sup>higher is cheaper</sup>')

        ctx = {
            'games': games,
            'graph_shop_size': fig_shop_size.to_html(full_html=False),
            'graph_shop_price': fig_shop_price.to_html(full_html=False),
        }
        return ctx
