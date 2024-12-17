import logging

from django.core.handlers.wsgi import WSGIRequest
from django.template.response import TemplateResponse
from django.views.generic import DetailView
from django_filters.views import FilterMixin
from django_tables2 import SingleTableView

from main.filters import GameFilter, ListingFilter, ShopFilter
from main.graphs import get_game_prices_graph
from main.models import Game, Listing, Shop
from main.selectors import get_best_savings_games, list_newest_games
from main.tables import GameTable, ListingTable, ShopTable

logger = logging.getLogger(__name__)


def home_view(request: WSGIRequest):
    """Home view."""
    savings = get_best_savings_games()
    latest = list_newest_games()
    ctx = {
        'savings': savings,
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
        """Get context."""
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
        """Get context."""
        ctx = super().get_context_data(**kwargs)
        ctx['listings'] = ctx['game'].listings.order_by('-in_stock', 'price').all()
        # graph for prices
        if prices_fig := get_game_prices_graph(self.object):
            ctx['prices_graph'] = prices_fig.to_html(full_html=False)
        else:
            ctx['prices_graph'] = None
        ctx['nav'] = 'games'
        return ctx
