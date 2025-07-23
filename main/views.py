import logging

from django.core.handlers.wsgi import WSGIRequest
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
from main.graphs import get_game_prices_graph, shop_price_index_graph
from main.models import Game, Listing, Shop
from main.selectors import (
    get_best_savings_games,
    list_bundle_listings,
    list_expensive_unique_by_shop,
    list_newest_games,
)
from main.shops import shop_enabled
from main.tables import GameTable, ListingTable, ShopTable

logger = logging.getLogger(__name__)


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
    template_name = 'main/listing_detail.html'
    context_object_name = 'listing'

    def get_context_data(self, **kwargs):
        """Get context."""
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

        inflation_graph = shop_price_index_graph(self.object)
        context['inflation_graph'] = inflation_graph.to_html(full_html=False)
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
        ctx['listings'] = ctx['game'].listings.order_by('-in_stock', 'price').all()
        # graph for prices
        if prices_fig := get_game_prices_graph(self.object):
            ctx['prices_graph'] = prices_fig.to_html(full_html=False)
        else:
            ctx['prices_graph'] = None
        ctx['nav'] = 'games'
        # Add current timestamp to context to ensure cache busting
        ctx['current_timestamp'] = timezone.now().timestamp()
        return ctx


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
