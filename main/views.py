import logging

from django.core.handlers.wsgi import WSGIRequest
from django.shortcuts import render
from django.views.generic import DetailView
from django_filters.views import FilterMixin
from django_tables2 import SingleTableView

from main.filters import GameFilter, ListingFilter, ShopFilter
from main.models import Game, Listing, Shop
from main.selectors import get_best_savings_games
from main.tables import GameTable, ListingTable, ShopTable

logger = logging.getLogger(__name__)


def home_view(request: WSGIRequest):
    """Home view."""
    savings = get_best_savings_games()
    # latest = get_latest_new_games()
    ctx = {
        'savings': savings,
        # 'latest': latest,
    }
    return render(request, 'main/home.html', ctx)


class ListingListView(SingleTableView, FilterMixin):
    model = Listing
    ordering = ['-in_stock']
    filterset_class = ListingFilter
    table_class = ListingTable
    template_name = 'main/list.html'
    paginate_by = 50

    def get_queryset(self):
        """Get query."""
        queryset = super().get_queryset()
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        """Get context."""
        context = super().get_context_data(**kwargs)
        context['filtering'] = self.filterset
        context['facet'] = 'listings'
        context['nav'] = 'listings'
        return context


class ListingDetailView(DetailView):
    model = Listing
    template_name = 'main/listing_detail.html'
    context_object_name = 'listing'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nav'] = 'listings'
        return context


class ShopListView(SingleTableView, FilterMixin):
    model = Shop
    ordering = ['name']
    filterset_class = ShopFilter
    table_class = ShopTable
    template_name = 'main/list.html'
    paginate_by = 50

    def get_queryset(self):
        """Get query."""
        queryset = super().get_queryset()
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        """Get context."""
        context = super().get_context_data(**kwargs)
        context['filtering'] = self.filterset
        context['facet'] = 'shops'
        context['nav'] = 'shops'
        return context


class ShopDetailView(DetailView):
    model = Shop
    template_name = 'main/shop-detail.html'
    context_object_name = 'shop'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nav'] = 'shops'
        return context


class GameListView(SingleTableView, FilterMixin):
    model = Game
    ordering = ['rank', '-shop_saving', '-shop_in_stock']
    filterset_class = GameFilter
    table_class = GameTable
    template_name = 'main/list.html'
    paginate_by = 50

    def get_queryset(self):
        """Get query."""
        queryset = super().get_queryset()
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        """Get context."""
        context = super().get_context_data(**kwargs)
        context['filtering'] = self.filterset
        context['facet'] = 'games'
        context['nav'] = 'games'
        return context


class GameDetailView(DetailView):
    model = Game
    queryset = Game.objects.prefetch_related('listings')
    template_name = 'main/game-detail.html'
    context_object_name = 'game'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nav'] = 'games'
        return context


# class GotView(CachedTemplateViewGet):
#     template_name = 'main/got.html'
#
#     def get_context_data(self, **kwargs):
#         """Get games of the month."""
#         award_groups = {}
#         to = now().year + 1
#         for year in reversed(range(c.START_GAME_OF_THE.year, to)):
#             half_year = make_aware(datetime(year, 7, 1))
#             award_groups[year] = {
#                 'year': Award.objects.filter(
#                     Q(type=AWARD_GAME_OF_THE_YEAR) & Q(awarded_at__year=year)
#                 ).first(),
#                 'top': Award.objects.filter(
#                     Q(type=AWARD_GAME_OF_THE_MONTH)
#                     & Q(awarded_at__year=year)
#                     & Q(awarded_at__lt=half_year)
#                 )
#                 .order_by('awarded_at')
#                 .all(),
#                 'bottom': Award.objects.filter(
#                     Q(type=AWARD_GAME_OF_THE_MONTH)
#                     & Q(awarded_at__year=year)
#                     & Q(awarded_at__gte=half_year)
#                 )
#                 .order_by('awarded_at')
#                 .all(),
#             }
#         ctx = {
#             'start_at': c.START_GAME_OF_THE,
#             'award_groups': award_groups,
#         }
#         return ctx
#
#
# class AboutView(CachedTemplateViewGet):
#     template_name = 'main/about.html'
#
#     def get_context_data(self, **kwargs):
#         """Get stats."""
#         # player updated
#         oldest_rec = Player.objects.aggregate(Min('rec_at'))['rec_at__min']
#         player_turnover = (now() - oldest_rec).days
#
#         # game added
#         days = 365
#         one_year = now() - timedelta(days=days)
#         total_games = Game.objects.filter(created_at__gte=one_year).count()
#
#         ctx = {
#             'total_games': total_games,
#             'player_turnover': player_turnover,
#             'min_used': c.REC_MIN_CUTOFF,
#             'max_used': c.REC_MAX_CUTOFF,
#         }
#         return ctx
#
#
# class ViewError(Exception):
#     """Bad view setup."""
#
#
# @method_decorator(cache_page(CACHE_DURATION), name='get')
# class CachedListViewGet(ListView):
#     pass
#
#
# @method_decorator(cache_page(CACHE_DURATION), name='get')
# class CachedDetailViewGet(DetailView):
#     pass
#
#
# class OrderingListView(ListView):
#     ordering = None
#
#     def get_ordering(self):
#         """Get ordering."""
#         if not self.ordering:
#             raise ViewError('Missing ordering on view')
#         return self.request.GET.get('o', self.ordering)
#
#     def get_context_data(self, *, object_list=None, **kwargs):
#         """Get ordering."""
#         ctx = super().get_context_data(object_list=object_list, **kwargs)
#         ctx['ordering'] = self.get_ordering()
#         return ctx
#
#
# class SearchListView(ListView):
#     search_by = None
#
#     def get_context_data(self, *, object_list=None, **kwargs):
#         """Get search query."""
#         ctx = super().get_context_data(object_list=object_list, **kwargs)
#         ctx['s'] = self.request.GET.get('s')
#         return ctx
#
#     def get_queryset(self):
#         """Get query from search."""
#         queryset = super().get_queryset()
#         search = self.request.GET.get('s')
#         if not self.search_by:
#             raise ViewError('Missing search_by on view.')
#         if search:
#             q = None
#             for val in search.split():
#                 params = {f'{self.search_by}__icontains': val}
#                 if not q:
#                     q = Q(**params)
#                 else:
#                     q.add(Q(**params), Q.OR)
#             queryset = queryset.filter(q)
#         return queryset
#
#
# class GameListView(OrderingListView, SearchListView, CachedListViewGet):
#     model = Game
#     paginate_by = 100
#     search_by = 'name'
#     queryset = Game.objects.exclude(hotness__isnull=True)
#     ordering = '-hotness'
#
#     def get_queryset(self):
#         """Get availability."""
#         queryset = super().get_queryset()
#         availability = int(self.request.GET.get('a', 1))
#         if not self.request.GET.get('s') and availability:
#             queryset = queryset.filter(shop_available=True)
#         return queryset
#
#     def get_context_data(self, *, object_list=None, **kwargs):
#         """Get percentiles."""
#         ctx = super().get_context_data(object_list=object_list, **kwargs)
#         ctx['weights_percentiles'] = c.WEIGHTS_CUTOFF
#         # show only available
#         ctx['available'] = 0 if self.request.GET.get('s') else int(self.request.GET.get('a', 1))
#         return ctx
#
#
# class GameDetailView(CachedDetailViewGet):
#     model = Game
#     context_object_name = 'game'
#
#     def get_context_data(self, **kwargs):
#         """Get game details."""
#         ctx = super().get_context_data(**kwargs)
#
#         # prev and next
#         ctx['prev'] = (
#             Game.objects.filter(rating__gt=self.object.rating).order_by('rating', '-rank').first()
#         )
#         ctx['next'] = (
#             Game.objects.filter(rating__lt=self.object.rating).order_by('-rating', 'rank').first()
#         )
#
#         # graph histogram
#         histogram = self.object.reviews.values('rating')
#         df = pd.DataFrame(list(histogram))
#         fig = px.box(df, y='rating')
#         fig.update_yaxes(tick0=1, dtick=1)
#         ctx['rating_graph'] = fig.to_html(full_html=False)
#
#         # graph daily
#         day_data = (
#             self.object.reviews.annotate(month=TruncMonth('reviewed_at'))
#             .order_by('month')
#             .values('month')
#             .annotate(cnt=Count('month'))
#             .values('month', 'cnt')
#         )
#         if day_data:
#             day_df = pd.DataFrame([{'Month': d['month'], 'Ratings': d['cnt']} for d in day_data])
#             day_fig = px.bar(day_df, x='Month', y='Ratings', title='Ratings per month')
#             ctx['day_graph'] = day_fig.to_html(full_html=False)
#
#         # graph for prices
#         if prices_fig := get_game_prices_bar(self.object):
#             ctx['prices_graph'] = prices_fig.to_html(full_html=False)
#         else:
#             ctx['prices_graph'] = None
#
#         yt_search = Search(f'board game review {self.object.name} {self.object.year}')
#         ctx['yt_results'] = [
#             {
#                 'embed_url': yt.embed_url,
#                 'title': yt.title,
#                 'author': yt.author,
#             }
#             for yt in yt_search.results
#         ][:6]
#
#         return ctx
#
#
# class PlayerListView(OrderingListView, SearchListView, CachedListViewGet):
#     model = Player
#     paginate_by = 100
#     ordering = '-last_review_at'
#     queryset = Player.objects.filter(reviews_cnt__gte=3)
#     search_by = 'nick'
#
#     def get_queryset(self) -> QuerySet:
#         """Get search."""
#         qs = super().get_queryset()
#         search = self.request.GET.get('s')
#         if not search:
#             qs = qs.filter(last_review_at__year__gt=c.SOME_YEARS_AGO)
#         return qs
#
#     def get_context_data(self, *args, object_list=None, **kwargs):
#         """Get time."""
#         ctx = super().get_context_data(*args, object_list=object_list, **kwargs)
#
#         # add graph for listing only (not on search)
#         # if not ctx['s']:
#         #     today = now()
#         #     days = Review.objects.values('player').annotate(
#         #         last_day=Max('reviewed_at')
#         #     ).order_by('player').values_list('last_day', flat=True)
#
#         ctx['some_years_ago'] = c.SOME_YEARS_AGO
#         return ctx
#
#
# class PlayerDetailView(DetailView):
#     model = Player
#     context_object_name = 'player'
#
#     def get_context_data(self, **kwargs):
#         """Get player detail."""
#         data = super().get_context_data(**kwargs)
#
#         data['weights'] = c.WEIGHTS
#         data['player_sizes'] = c.PLAYERS_SIZES
#
#         # graph: vs
#         fig_data = [
#             {'Actual': r.rating, 'Expected': r.predicted, 'Name': r.game.name}
#             for r in self.object.reviews.all()
#             if r.rating and r.predicted
#         ]
#         if fig_data:
#             min_est = min([f['Expected'] for f in fig_data])
#             max_est = max([f['Expected'] for f in fig_data])
#             df = pd.DataFrame(fig_data)
#             fig = px.scatter(
#                 df, x='Expected', y='Actual', hover_name='Name', title='Actual vs expected rating'
#             )
#             fig.add_shape(type='line', x0=min_est, y0=min_est, x1=max_est, y1=max_est)
#             fig.update_yaxes(dtick=1)
#             fig.update_xaxes(dtick=1)
#             data['graph'] = fig.to_html(full_html=False)
#
#         # graph: heatmap
#         if self.object.reviews.count():
#             reviews = list(
#                 self.object.reviews.filter(
#                     predicted__isnull=False,
#                 ).all()
#             )
#             reviews.sort(key=attrgetter('predicted'), reverse=True)
#             reviews.sort(key=attrgetter('rating'), reverse=True)
#             data['reviews'] = reviews
#
#             # player count
#             p_data = {
#                 'Very Light': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
#                 'Light': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
#                 'Medium': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
#                 'Heavy': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
#                 'Very Heavy': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
#             }
#             for review in reviews:
#                 if review.game.best_min_players is None or review.game.best_max_players is None:
#                     continue
#                 for p in range(review.game.best_min_players, review.game.best_max_players + 1):
#                     if p in p_data[review.game.weight_tag]:
#                         p_data[review.game.weight_tag][p] += 1
#             # layout = {'xaxis': {'ticks': [int(x) for x in df['player_count']]}}
#             # fig = px.bar(df, x='player_count', y='count',
#             #   title='Number of games per best player count')
#             h_data = [list(p.values()) for p in p_data.values()]
#             fig = px.imshow(
#                 h_data,
#                 x=[1, 2, 3, 4, 5],
#                 y=['very light', 'light', 'medium', 'heavy', 'very heavy'],
#                 labels={'x': 'Player count', 'y': 'Complexity'},
#                 title='Heatmap of player games',
#             )
#             data['heat'] = fig.to_html(full_html=False)
#
#         # split by status
#         data['collection'] = [
#             ('Owned', self.object.reviews.filter(status=c.REVIEW_STATUS_OWN).all()),
#             ('Sold', self.object.reviews.filter(status=c.REVIEW_STATUS_PREV_OWNED).all()),
#             ('Wanted', self.object.reviews.filter(status=c.REVIEW_STATUS_WISH_LIST).all()),
#             ('Other', self.object.reviews.filter(status=c.REVIEW_STATUS_NONE).all()),
#         ]
#
#         return data
#
#
# def player_predict_view(request, pk):
#     """Prevent spam by checking requested_at is empty."""
#     player = Player.objects.get(pk=pk)
#     if not player.redo_requested_at:
#         player.redo_requested_at = now()
#         player.redo_started_at = None
#         player.save()
#     return redirect(player)
#
#
# class CountryView(CachedTemplateViewGet):
#     template_name = 'main/country.html'
#
#     def get_context_data(self, **kwargs):  # noqa PLR0915 PLR0912
#         """Get country stats."""
#         start_of_year = datetime(2022, 1, 1)
#         start_of_last_year = datetime(2021, 1, 1)
#         data = super().get_context_data(**kwargs)
#         players = Player.objects.filter(
#             country=c.COUNTRY_SOUTH_AFRICA, last_review_at__gte=start_of_year
#         ).all()
#
#         data['players'] = players
#
#         games = defaultdict(list)
#         players_gone = (
#             Player.objects.filter(
#                 country=c.COUNTRY_SOUTH_AFRICA,
#                 last_review_at__gte=start_of_last_year,
#             )
#             .exclude(pk__in=[p.pk for p in players])
#             .count()
#         )
#         data['players_gone'] = players_gone
#
#         reviews_per_player = []
#         new_players = 0
#
#         area_typos = 0
#         cntr_provinces = Counter()
#         cntr_cities = Counter()
#         for player in players:
#             # new players
#             if not player.reviews.filter(created_at__lt=start_of_year).count():
#                 new_players += 1
#
#             player_reviews = player.reviews.filter(created_at__gte=start_of_year).all()
#             for review in player_reviews:
#                 games[review.game].append(review.rating)
#
#             # get reviews per player
#             reviews_per_player.append((player.nick, len(player_reviews)))
#
#             # get area counts
#             if not player.area:
#                 continue
#             area = player.area.replace(', South Africa', '')
#             places = area.split(',')
#             if len(places) != c.SPLIT_SIZE:
#                 if places in [
#                     ['Pre'],
#                     ['KwaZulu-Natal'],
#                     ['KwaZulu Natal'],
#                     ['Gauteng'],
#                     ['Haw'],
#                     ['Joburg & Cape Town'],
#                     ['Kwa-Zulu Natal'],
#                     ['Western Cape'],
#                 ]:
#                     area_typos += 1
#                     continue
#                 if places in [
#                     ['Cape Town'],
#                     ['Blouberg'],
#                     ['Stellenridge', ' Cape Town', ' Western Cape'],
#                     ['Brackenfell'],
#                     ['Tokai', ' Cape Town', ' Western Cape'],
#                 ]:
#                     area_typos += 1
#                     places = [c.CITY_CAPE_TOWN, c.PROVINCE_WESTERN_CAPE]
#                 elif places in [['Stellenbos']]:
#                     area_typos += 1
#                     places = [c.CITY_STELLENBOSCH, c.PROVINCE_WESTERN_CAPE]
#                 elif places in [['Pietermaritzburg']]:
#                     area_typos += 1
#                     places = [c.CITY_PIETERMARITZBURG, c.PROVINCE_KWAZULU_NATAL]
#                 elif places in [['Lephalale']]:
#                     area_typos += 1
#                     places = [c.CITY_ELLISRAS, c.PROVINCE_LIMPOPO]
#                 elif places in [['Bloemfontein']]:
#                     area_typos += 1
#                     places = [c.CITY_BLOEMFONTEIN, c.PROVINCE_FREE_STATE]
#                 elif places in [['Johannesburg']]:
#                     area_typos += 1
#                     places = [c.CITY_JOHANNESBURG, c.PROVINCE_GAUTENG]
#                 elif places in [['Potchefstroom']]:
#                     area_typos += 1
#                     places = [c.CITY_POTCHEFSTROOM, c.PROVINCE_NORTH_WEST]
#                 elif places in [['La Lucia', ' Durban', ' KwaZulu-Natal'], ['Durban']]:
#                     area_typos += 1
#                     places = [c.CITY_DURBAN, c.PROVINCE_KWAZULU_NATAL]
#                 elif places in [['Georg']]:
#                     area_typos += 1
#                     places = [c.CITY_GEORGE, c.PROVINCE_WESTERN_CAPE]
#                 elif places in [['Lyttelton']]:
#                     area_typos += 1
#                     places = [c.CITY_CENTURION, c.PROVINCE_GAUTENG]
#                 elif places in [['Port Elizabe']]:
#                     area_typos += 1
#                     places = [c.CITY_PORT_ELIZABETH, c.PROVINCE_EASTERN_CAPE]
#                 elif places in [['Benon']]:
#                     area_typos += 1
#                     places = [c.CITY_BENONI, c.PROVINCE_GAUTENG]
#                 else:
#                     raise ValueError(f'expected 2 values for area: {places}')
#
#             province = places[1].strip().title()
#             if province not in c.PROVINCES_LIST:
#                 if province in ['Florid', 'Unspecified', 'Hampshire', 'Les']:
#                     area_typos += 1
#                     continue
#                 if province in ['North Wes', 'North-Wes']:
#                     area_typos += 1
#                     province = c.PROVINCE_NORTH_WEST
#                 elif province in ['Westkap', 'Cape', 'Western Province', 'Kuilsrivie']:
#                     area_typos += 1
#                     province = c.PROVINCE_WESTERN_CAPE
#                 elif province in ['Kzn', 'Kwa-Zulu Natal', 'Kwazulu Natal']:
#                     area_typos += 1
#                     province = c.PROVINCE_KWAZULU_NATAL
#                 elif province in ['Guateng']:
#                     area_typos += 1
#                     province = c.PROVINCE_GAUTENG
#                 elif province in ['Mpumalang']:
#                     area_typos += 1
#                     province = c.PROVINCE_MPUMALANGA
#                 elif province in ['Freestate']:
#                     area_typos += 1
#                     province = c.PROVINCE_FREE_STATE
#                 elif province in ['Limpop']:
#                     area_typos += 1
#                     province = c.PROVINCE_LIMPOPO
#                 elif province in ['South-']:
#                     area_typos += 1
#                     province = c.PROVINCE_GAUTENG
#                 elif province in ['Northen Province']:
#                     area_typos += 1
#                     province = c.PROVINCE_NORTHERN_CAPE
#                 else:
#                     raise ValueError(f'expected province: {province}')
#             cntr_provinces.update([province])
#
#             data['new_players'] = new_players
#
#             city = places[0].strip().title()
#             if city not in c.CITIES[province]:
#                 if city in ['Johannesburgo', 'Sandton', 'Johanneburg', 'Newtown']:
#                     area_typos += 1
#                     city = c.CITY_JOHANNESBURG
#                 elif city in ['Kapstadt', 'Bellville', 'Capetown', 'Durbanville', 'Brackenfell']:
#                     area_typos += 1
#                     city = c.CITY_CAPE_TOWN
#                 elif city in ['Polokwane', 'Polokwane City']:
#                     area_typos += 1
#                     city = c.CITY_PIETERSBURG
#                 elif city in ['Makhanda']:
#                     area_typos += 1
#                     city = c.CITY_GRAHAMSTOWN
#                 elif city in ['Pietersburg'] or city in ['Pietersburg']:
#                     area_typos += 1
#                     province = c.PROVINCE_MPUMALANGA
#                 elif city in ['Pretoria/Centurion']:
#                     area_typos += 1
#                     province = c.CITY_PRETORIA
#                 else:
#                     raise ValueError(f'Expected city in {province}: {city}')
#             cntr_cities.update([city])
#
#         data['typos'] = area_typos
#
#         df_provinces = pd.DataFrame(cntr_provinces.most_common(10), columns=['province', 'cnt'])
#         fig_provinces = px.bar(
#             df_provinces,
#             x='province',
#             y='cnt',  # histfunc='sum', #range_x=(0, 10),
#             labels={'province': 'Provinces', 'cnt': 'Count'},
#             title='Histogram of provinces',
#         )
#         # df_provinces.update_traces(nbinsx=20, autobinx=False)
#         data['graph_provinces'] = fig_provinces.to_html(full_html=False)
#
#         df_cities = pd.DataFrame(cntr_cities.most_common(20), columns=['city', 'cnt'])
#         fig_cities = px.bar(
#             df_cities,
#             x='city',
#             y='cnt',  # histfunc='sum', #range_x=(0, 10),
#             labels={'city': 'Cities', 'cnt': 'Count'},
#             title='Histogram of cities',
#         )
#         # df_cities.update_traces(nbinsx=20, autobinx=False)
#         data['graph_cities'] = fig_cities.to_html(full_html=False)
#
#         reviews = Review.objects.filter(player__country=c.COUNTRY_SOUTH_AFRICA).all()
#         data['reviews'] = reviews
#
#         reviews_per_player.sort(key=itemgetter(1), reverse=True)
#         df_top_raters = pd.DataFrame(reviews_per_player[:50], columns=['player', 'cnt'])
#         fig_top_raters = px.bar(
#             df_top_raters,
#             x='cnt',
#             y='player',  # histfunc='sum', #range_x=(0, 10),
#             labels={'player': 'Player', 'cnt': 'Ratings made'},
#             title='Top 50 raters',
#             orientation='h',
#             height=1200,
#         )
#         # df_cities.update_traces(nbinsx=20, autobinx=False)
#         data['graph_top_raters'] = fig_top_raters.to_html(full_html=False)
#
#         data['games'] = games
#         games_rating_rated = [(g.name, len(rs), sum(rs) / len(rs)) for g, rs in games.items()]
#         df_grr = pd.DataFrame(games_rating_rated, columns=['game', 'count', 'rating'])
#         fig_grr = px.scatter(
#             df_grr,
#             x='count',
#             y='rating',
#             hover_name='game',
#             title='Number of ratings vs average rating score',
#             height=600,
#         )
#         data['graph_grr'] = fig_grr.to_html(full_html=False)
#
#         for game, ratings in games.items():
#             game.total_ratings = len(ratings)
#             game.average_rating = sum(ratings) / len(ratings)
#             game.score = game.total_ratings * game.average_rating
#
#         top_games = [g for g in games]
#         top_games.sort(key=attrgetter('score'), reverse=True)
#         data['top_games'] = top_games[:50]
#
#         avg_ratings = sum(g.total_ratings for g in games) / len(games)
#         data['avg_ratings'] = avg_ratings
#         best_games = [g for g in games if g.total_ratings > avg_ratings]
#         best_games.sort(key=attrgetter('average_rating'), reverse=True)
#         data['best_games'] = best_games[:20]
#
#         # games per year
#         cntr_gpy = Counter([g.year for g in games if g.year >= start_of_year.year - 20])
#         df_gpy = pd.DataFrame(cntr_gpy.most_common(999), columns=['year', 'cnt'])
#         fig_gpy = px.bar(
#             df_gpy,
#             x='year',
#             y='cnt',  # histfunc='sum', #range_x=(0, 10),
#             labels={'year': 'Release year of game', 'cnt': 'Number of games rated'},
#             title='Histogram of games by year',
#         )
#         # df_gpy.update_traces(nbinsx=20, autobinx=False)
#         data['graph_gpy'] = fig_gpy.to_html(full_html=False)
#
#         # recs
#         top_recs = list()
#         recs_per_game = Counter([r.game for p in players for r in p.recs.all()])
#         for game, recs in recs_per_game.most_common(20):
#             game.rsa_recs = recs
#             top_recs.append(game)
#         data['top_recs'] = top_recs
#
#         # top ranked
#         points = [25, 18, 15, 12, 8, 6, 4, 2, 1, 1]
#         top_ranked_last_year = defaultdict(lambda: 0)
#         last_players = Player.objects.filter(
#             country=c.COUNTRY_SOUTH_AFRICA,
#             last_review_at__gte=start_of_last_year,
#             last_review_at__lte=start_of_year,
#         ).all()
#         for last_player in last_players:
#             last_reviews = (
#                 last_player.reviews.annotate(cutoff=Min('created_at', 'reviewed_at'))
#                 .filter(cutoff__lte=start_of_year)
#                 .order_by('-rating', '-created_at')
#                 .all()
#             )
#             for point, last_review in zip(points, last_reviews, strict=False):
#                 top_ranked_last_year[last_review.game] += point
#         top_rank_last = list(top_ranked_last_year.items())
#         top_rank_last.sort(key=itemgetter(1), reverse=True)
#         top_rank_last = {gr[0]: ix + 1 for ix, gr in enumerate(top_rank_last)}
#
#         top_ranked_this_year = defaultdict(lambda: 0)
#         for player in players:
#             reviews = player.reviews.order_by('-rating', '-created_at').all()
#             for point, review in zip(points, reviews, strict=False):
#                 top_ranked_this_year[review.game] += point
#         rankings = list(top_ranked_this_year.items())
#         rankings.sort(key=itemgetter(1), reverse=True)
#         final_rankings = []
#         for ix, ranking in enumerate(rankings[:100]):
#             final_rankings.append(
#                 (
#                     ranking[0],
#                     ranking[1],
#                     ix + 1,
#                     'New'
#                     if not top_rank_last.get(ranking[0])
#                     else top_rank_last[ranking[0]] - ix + 1,
#                 )
#             )
#         data['rankings'] = final_rankings[::-1]
#
#         return data
#
#
# class ReviewView(CachedTemplateViewGet):
#     template_name = 'main/reviews.html'
#
#     def get_context_data(self, **kwargs):
#         """Get review graphs."""
#         data = super().get_context_data(**kwargs)
#
#         fig_daily = get_reviews_daily_count_graph()
#         data['graph_day'] = fig_daily.to_html(full_html=False)
#
#         fig_cnt = get_reviews_count_per_player()
#         data['graph_reviews_cnt'] = fig_cnt.to_html(full_html=False)
#
#         fig_rating = get_reviews_histogram_ratings()
#         data['graph_rating'] = fig_rating.to_html(full_html=False)
#
#         return data


# def redo_prediction_view(request: WSGIRequest):
#     """Redo next prediction."""
#     load_next_and_predict()
#     return HttpResponse('Success!', status=200)
