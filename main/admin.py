import logging

from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from main.forms import LookupForm
from main.games import search_bgg, update_game_shop_prices
from main.models import Game, Label, Listing, PageView, Price, Scrapelog, Shop
from main.selectors import list_listings_without_games

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
        'updated_at',
    )
    list_filter = ('shop__name', 'in_stock')
    list_editable = ('bgg_id',)
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
            if listing:
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
                    'is_accessory': listing.is_accessory,
                }
                form = LookupForm(initial=initial)
                ctx['listing'] = listing
                ctx['bgg'] = bgg
                ctx['form'] = form
            else:
                ctx['finished'] = True

        ctx['remaining'] = list_listings_without_games().count()

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
    list_display = ('label', 'name_img', 'year', 'rank', 'shop_best', 'shop_price', 'shop_mean')
    list_filter = ['label']
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


@admin.register(Scrapelog)
class ScrapelogAdmin(admin.ModelAdmin):
    list_display = ['day', 'target', 'outcome', 'duration', 'scraped_at']
    list_filter = [
        'target',
    ]
    list_editable = []
    search_fields = ['outcome']
    readonly_fields = ['outcome', 'duration']
    ordering = ['-day', 'target']


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ['id', 'day', 'ip', 'game']
    search_fields = ['ip', 'game__name']
    ordering = ['-day', 'game', 'ip']
