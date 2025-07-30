import logging

from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from main.forms import LookupForm
from main.games import search_bgg, update_game_shop_prices
from main.graphs import get_ip_request_chart
from main.models import Game, Label, Listing, PageView, Price, Scrapelog, Shop, VisitorLog
from main.selectors import list_listings_rated_today, list_listings_without_games

logger = logging.getLogger(__name__)


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'type']
    list_filter = ['type']
    search_fields = ['id', 'name']
    ordering = ['type', 'name']


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = []
    list_editable = []
    search_fields = []
    readonly_fields = ('name',)
    ordering = ('name',)


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'shop',
        'bgg_id',
        'bgg_missing',
        'pic',
        'name_link',
        'category',
        'in_stock',
        'price',
        'priced_at',
        'url',
        'last_price',
        'view_prices_link',
    )
    list_filter = ('shop__name', 'in_stock', 'category')
    list_editable = ('bgg_id', 'category')
    search_fields = ('name', 'url')
    readonly_fields = ('shop', 'in_stock', 'price', 'priced_at')
    ordering = (
        'bgg_missing',
        'created_at',
    )

    change_list_template = 'admin/listing_change_list.html'

    def pic(self, obj: Listing):
        """Pic."""
        return format_html(f'<img src="{obj.img}" style="width:3em;height:auto;padding:0.1em;"/>')

    @admin.display(ordering='name')
    def name_link(self, obj: Listing):
        """Name link."""
        return format_html(
            """
            <a href="{url}" target="_blank">
                {name}
            </a>
            """,
            url=obj.url,
            name=obj.name,
        )

    @admin.display(ordering='price')
    def last_price(self, obj: Listing):
        """Last price."""
        last_price = obj.prices.filter(in_stock=True).last()
        if not last_price:
            return 'never'
        return last_price.price

    @admin.display()
    def view_prices_link(self, obj):
        """Custom link to go to prices."""
        url = reverse('admin:main_price_changelist') + f'?listing__id__exact={obj.id}'
        return format_html('<a href="{}" target="_blank">View Prices</a>', url)

    def get_urls(self):
        """Get urls."""
        urls = super().get_urls()
        custom_urls = [
            path(r'lookup/', self.admin_site.admin_view(self.lookup_view), name='listing-lookup')
        ]
        return custom_urls + urls

    def lookup_view(self, request):
        """Lookup view."""
        ctx = dict(
            self.admin_site.each_context(request),
        )

        if request.method == 'POST':
            form = LookupForm(request.POST)
            if form.is_valid():
                form.save()
                return redirect('admin:listing-lookup')
        else:
            listing = list_listings_without_games().first()
            if not listing.game:
                bgg = search_bgg(listing.bgg_id or listing.name)
            else:
                bgg = {
                    'name': listing.game.name,
                    'bgg_id': listing.bgg_id,
                    'missing': False,
                    'image': listing.game.img,
                    'search': f'https://boardgamegeek.com/geeksearch.php?'
                    f'objecttype=boardgame&action=search&q={listing.bgg_id}',
                }
            initial = {
                'listing_id': listing.id,
                'bgg_id': bgg.get('bgg_id'),
                'is_missing': listing.bgg_missing,
                'category': listing.category,
            }
            form = LookupForm(initial=initial)
            ctx['listing'] = listing
            ctx['bgg'] = bgg
            ctx['form'] = form

        ctx['remaining'] = list_listings_without_games().count()
        ctx['count_today'] = list_listings_rated_today().count()

        return render(request, 'admin/listing_lookup.html', ctx)


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ['listing', 'day', 'in_stock', 'price']
    list_filter = ['listing__shop__name', 'in_stock']
    list_editable = ['in_stock', 'price']
    search_fields = ['listing__name']
    readonly_fields = []
    ordering = ['-day']


@admin.action(description='Recalculate shop prices')
def update_game_shop_prices_action(modeladmin, request, queryset):
    """Scrape game command."""
    for obj in queryset:
        update_game_shop_prices(obj)


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        'label',
        'name_img',
        'year',
        'rank',
        'shop_best',
        'shop_price',
        'shop_mean',
        'view_listings_link',
    )
    list_filter = ['label', 'shop_best']
    list_editable = []
    search_fields = ['name']
    readonly_fields = ('name',)
    ordering = ('name',)
    actions = [update_game_shop_prices_action]

    def name_img(self, obj: Game):
        """Get name and img."""
        return format_html(
            """
            <img src="{img}" style="width:3em;height:auto;padding:0 1em 0 0;float:left;"/>
            {name}
            """,
            img=obj.img,
            name=obj.name,
        )

    def view_listings_link(self, obj):
        """Custom link to filter listings for the current game."""
        # Build the URL for the filtered ListingAdmin
        url = reverse('admin:main_listing_changelist') + f'?game__id__exact={obj.id}'
        return format_html('<a href="{}" target="_blank">View Listings</a>', url)

    view_listings_link.short_description = 'Listings'


@admin.register(Scrapelog)
class ScrapelogAdmin(admin.ModelAdmin):
    list_display = ['day', 'target', 'outcome', 'duration', 'scraped_at']
    list_filter = [
        'target',
    ]
    list_editable = []
    search_fields = ['outcome']
    readonly_fields = ['outcome', 'duration']
    ordering = ['outcome', '-scraped_at']


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ['id', 'day', 'ip', 'game']
    search_fields = ['ip', 'game__name']
    ordering = ['-day', 'game', 'ip']


@admin.register(VisitorLog)
class VisitorLogAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'path', 'timestamp', 'referrer_short', 'user_agent_short')
    list_filter = ('timestamp',)
    search_fields = ('ip_address', 'path', 'referrer', 'user_agent')
    readonly_fields = ('ip_address', 'path', 'timestamp', 'referrer', 'user_agent')
    ordering = ('-timestamp',)
    change_list_template = 'admin/visitorlog_change_list.html'

    def referrer_short(self, obj):
        """Get referrer short."""
        cut_off = 50
        return (
            obj.referrer[:cut_off] + '...'
            if obj.referrer and len(obj.referrer) > cut_off
            else obj.referrer
        )

    referrer_short.short_description = 'Referrer'

    def user_agent_short(self, obj):
        """Get user agent short."""
        cut_off = 50
        return (
            obj.user_agent[:cut_off] + '...'
            if obj.user_agent and len(obj.user_agent) > cut_off
            else obj.user_agent
        )

    user_agent_short.short_description = 'User Agent'

    def get_urls(self):
        """Get urls."""
        urls = super().get_urls()
        custom_urls = [
            path(
                r'visitorlog/graph',
                self.admin_site.admin_view(self.visitorlog_graph_view),
                name='visitorlog-graph',
            )
        ]
        return custom_urls + urls

    def visitorlog_graph_view(self, request):
        """Graph of visitor log."""
        fig = get_ip_request_chart()
        chart_html = fig.to_html(
            full_html=False, include_plotlyjs='cdn', config={'responsive': True}
        )

        ctx = dict(
            self.admin_site.each_context(request),
            chart=chart_html,
        )
        return render(request, 'admin/visitorlog_graph.html', ctx)
