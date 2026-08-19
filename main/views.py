import logging
from decimal import Decimal, InvalidOperation

from django.core.handlers.wsgi import WSGIRequest
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.generic import DetailView
from django_filters.views import FilterMixin
from django_tables2 import SingleTableView

from main.constants import (
    CATEGORY_ACCESSORIES,
    CATEGORY_CARD_GAME,
    CATEGORY_OTHER,
    CATEGORY_RPG,
    CATEGORY_TABLETOP,
)
from main.filters import GameFilter, ListingFilter, ShopFilter
from main.graphs import (
    get_game_prices_graph,
    get_listing_prices_graph,
    legend_entries,
    series_track_heights,
    shop_price_index_graph,
)
from main.models import Game, Listing, Shop
from main.selectors import (
    get_best_savings_games,
    get_last_scrape,
    list_bundle_listings,
    list_expensive_unique_by_shop,
    list_newest_games,
)
from main.shops import shop_enabled
from main.tables import GameTable, ListingTable, ShopTable

logger = logging.getLogger(__name__)

# Charts are printed into the sheet, so plotly's own chrome stays off and the
# figure resizes with its ruled container instead of holding a fixed width.
PLOTLY_CONFIG = {'responsive': True, 'displayModeBar': False}

# A browser keeps its own pin list in localStorage. It never sends more than the
# last few, and anything past that is dropped rather than trusted.
PIN_MAX = 6


def home_view(request: WSGIRequest):
    """Home view."""
    savings = get_best_savings_games()
    bundles = list_bundle_listings()
    latest = list_newest_games()
    ctx = {
        'savings': savings,
        'bundles': bundles,
        'latest': latest,
    }
    return TemplateResponse(request, 'main/home.html', ctx)


def _parse_pins(raw: str) -> list[tuple[int, Decimal | None]]:
    """Read the `pk:price` pin list a browser sends, newest pin first."""
    pins = []
    for chunk in raw.split(',')[:PIN_MAX]:
        pk, _, pinned = chunk.partition(':')
        if not pk.isdigit():
            continue
        try:
            price = Decimal(pinned) if pinned else None
        except InvalidOperation:
            price = None
        pins.append((int(pk), price))
    return pins


def pinned_games_view(request: WSGIRequest):
    """Return the tray of games this browser has pinned, with their price moves."""
    pins = _parse_pins(request.GET.get('pins', ''))
    games = Game.objects.filter(pk__in=[pk for pk, _ in pins]).select_related('shop_best')
    by_pk = {game.pk: game for game in games}
    pinned = []
    for pk, pinned_price in pins:
        game = by_pk.get(pk)
        if not game:
            continue
        # Carried for the template only: what the game cost when it was pinned,
        # and which way it has moved since.
        game.pinned_price = pinned_price
        game.pinned_move = (
            game.shop_price - pinned_price
            if pinned_price and game.shop_in_stock and game.shop_price is not None
            else None
        )
        pinned.append(game)
    return TemplateResponse(request, 'main/snippet_pinned_group.html', {'pinned': pinned})


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
        queryset = queryset.exclude(
            category__in=[
                CATEGORY_CARD_GAME,
                CATEGORY_TABLETOP,
                CATEGORY_RPG,
                CATEGORY_ACCESSORIES,
                CATEGORY_OTHER,
            ]
        )
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
    queryset = Listing.objects.select_related('shop', 'game')
    template_name = 'main/listing_detail.html'
    context_object_name = 'listing'

    def get_context_data(self, **kwargs):
        """Get context."""
        context = super().get_context_data(**kwargs)
        context['nav'] = 'listings'
        listing = self.object
        # price history graph
        if prices_fig := get_listing_prices_graph(listing):
            context['prices_graph'] = prices_fig.to_html(full_html=False, config=PLOTLY_CONFIG)
        # other listings for the same game
        if listing.game:
            context['sibling_listings'] = (
                listing.game.listings.filter(in_stock=True)
                .exclude(pk=listing.pk)
                .select_related('shop')
                .order_by('price')[:5]
            )
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
        open_shop_names = [k for k, v in shop_enabled.items() if v]
        queryset = super().get_queryset()
        queryset = queryset.filter(name__in=open_shop_names)
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
        """Get context."""
        context = super().get_context_data(**kwargs)
        context['nav'] = 'shops'
        context['unique'] = list_expensive_unique_by_shop(self.object)
        context['last_scrape'] = get_last_scrape(self.object)

        inflation_graph = shop_price_index_graph(self.object)
        context['inflation_graph'] = inflation_graph.to_html(full_html=False, config=PLOTLY_CONFIG)
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
        queryset = queryset.exclude(
            listings__category__in=[
                CATEGORY_CARD_GAME,
                CATEGORY_TABLETOP,
                CATEGORY_RPG,
                CATEGORY_ACCESSORIES,
                CATEGORY_OTHER,
            ]
        )
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
        """Get context."""
        ctx = super().get_context_data(**kwargs)
        # Materialised: the sheet reads the ends of this list to decide whether
        # the in-stock and out-of-stock rosters are empty.
        ctx['listings'] = list(
            ctx['game'].listings.select_related('shop').order_by('-in_stock', 'price')
        )
        # Prices graph is loaded lazily via htmx — see game-prices-graph URL.
        ctx['nav'] = 'games'
        # Add current timestamp to context to ensure cache busting
        ctx['current_timestamp'] = timezone.now().timestamp()
        return ctx


def game_prices_graph_view(request: WSGIRequest, pk: int):
    """Return the game prices graph fragment for the requested period."""
    period = request.GET.get('period', 'recent')
    if period not in ('recent', 'max'):
        period = 'recent'
    game = get_object_or_404(Game, pk=pk)
    prices_fig = get_game_prices_graph(game, period=period)
    ctx = {
        'game': game,
        'prices_graph': (
            prices_fig.to_html(full_html=False, config=PLOTLY_CONFIG) if prices_fig else None
        ),
        'prices_period': period,
        # A blank track keeps the height plotly gave it; a real one is sized by
        # how many shop entries its key has to print.
        'track_heights': (
            series_track_heights(legend_entries(prices_fig))
            if prices_fig and prices_fig.data
            else None
        ),
    }
    return TemplateResponse(request, 'main/snippet_game_prices_graph.html', ctx)


class CardListView(SingleTableView, FilterMixin):
    model = Listing
    ordering = ['-in_stock', '-bgg_looked_at', '-updated_at', '-created_at']
    filterset_class = ListingFilter
    table_class = ListingTable
    template_name = 'main/list.html'
    paginate_by = 50

    def get_queryset(self):
        """Get query."""
        queryset = super().get_queryset()
        queryset = queryset.filter(category=CATEGORY_CARD_GAME)
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        """Get context."""
        context = super().get_context_data(**kwargs)
        context['filtering'] = self.filterset
        context['facet'] = 'Card Games'
        context['nav'] = 'card'
        return context


class TabletopListView(SingleTableView, FilterMixin):
    model = Listing
    ordering = ['-in_stock', '-bgg_looked_at', '-updated_at', '-created_at']
    filterset_class = ListingFilter
    table_class = ListingTable
    template_name = 'main/list.html'
    paginate_by = 50

    def get_queryset(self):
        """Get query."""
        queryset = super().get_queryset()
        queryset = queryset.filter(category=CATEGORY_TABLETOP)
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        """Get context."""
        context = super().get_context_data(**kwargs)
        context['filtering'] = self.filterset
        context['facet'] = 'Tabletop'
        context['nav'] = 'tabletop'
        return context


class RpgListView(SingleTableView, FilterMixin):
    model = Listing
    ordering = ['-in_stock', '-bgg_looked_at', '-updated_at', '-created_at']
    filterset_class = ListingFilter
    table_class = ListingTable
    template_name = 'main/list.html'
    paginate_by = 50

    def get_queryset(self):
        """Get query."""
        queryset = super().get_queryset()
        queryset = queryset.filter(category=CATEGORY_RPG)
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        """Get context."""
        context = super().get_context_data(**kwargs)
        context['filtering'] = self.filterset
        context['facet'] = 'RPG'
        context['nav'] = 'rpg'
        return context


class AccessoriesListView(SingleTableView, FilterMixin):
    model = Listing
    ordering = ['-in_stock', '-bgg_looked_at', '-updated_at', '-created_at']
    filterset_class = ListingFilter
    table_class = ListingTable
    template_name = 'main/list.html'
    paginate_by = 50

    def get_queryset(self):
        """Get query."""
        queryset = super().get_queryset()
        queryset = queryset.filter(category=CATEGORY_ACCESSORIES)
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        """Get context."""
        context = super().get_context_data(**kwargs)
        context['filtering'] = self.filterset
        context['facet'] = 'accessories'
        context['nav'] = 'accessories'
        return context


class OtherListView(SingleTableView, FilterMixin):
    model = Listing
    ordering = ['-in_stock', '-bgg_looked_at', '-updated_at', '-created_at']
    filterset_class = ListingFilter
    table_class = ListingTable
    template_name = 'main/list.html'
    paginate_by = 50

    def get_queryset(self):
        """Get query."""
        queryset = super().get_queryset()
        queryset = queryset.filter(category=CATEGORY_OTHER)
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        """Get context."""
        context = super().get_context_data(**kwargs)
        context['filtering'] = self.filterset
        context['facet'] = 'Other'
        context['nav'] = 'other'
        return context
