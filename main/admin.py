import logging

from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from main.forms import LookupForm
from main.games import search_bgg, update_game_shop_prices
from main.models import Game, Label, Listing, Price, Scrapelog, Shop
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
        'in_stock',
        'price',
        'priced_at',
        'url',
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
                    'bgg_id': bgg['bgg_id'] if bgg else '',
                    'is_missing': bgg['missing'],
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


# @admin.action(description='Scrape games')
# def scrape_game_cmd(modeladmin, request, queryset):
#     """Scrape game command."""
#     for obj in queryset:
#         scrape_game(obj)
#
#
# @admin.action(description='Scrape players')
# def scrape_player_cmd(modeladmin, request, queryset):
#     """Scrape player command."""
#     for obj in queryset:
#         scrape_player(obj)
#
#
# @admin.action(description='Predict players')
# def predict_player_cmd(modeladmin, request, queryset):
#     """Predict player command."""
#     game_ids = Game.objects.values_list('id', flat=True)
#     for obj in queryset:
#         predict_player(obj, game_ids)
#
#
# @admin.action(description='Update shop game prices')
# def update_game_shop_prices_cmd(modeladmin, request, queryset):
#     """Update game shop prices command."""
#     games = set([g for g in queryset])
#     for game in games:
#         update_game_shop_prices(game)
#
#
# @admin.register(Game)
# class GameAdmin(admin.ModelAdmin):
#     list_display = (
#         'id',
#         'hotness',
#         'rank',
#         'title',
#         'year',
#         'min_age',
#         'players',
#         'time',
#         'reviews_cnt_fmt',
#         'scraped_at',
#         'bgg_id',
#         'shop_price',
#         'shop_updated_at',
#     )
#     # list_filter = ('shop_available',)
#     ordering = ('-hotness',)
#     actions = (scrape_game_cmd, update_game_shop_prices_cmd)
#     search_fields = ('name',)
#     exclude = ('shop_available', 'shop_price', 'shop_saving', 'hotness', 'sim_cluster')
#
#     def reviews_cnt_fmt(self, obj: Game):
#         """Format reviews count."""
#         url = reverse('admin:main_review_changelist')
#         return format_html(f'<a href="{url}?game={obj.pk}">{obj.reviews_cnt}</a>')
#
#     def title(self, obj: Game):
#         """Title."""
#         return format_html(
#             f'<p><span style="float:left; min-width:100px"><img height="50" src="{obj.img}"/></span>{obj.name}<br/><small>{obj.pitch}</small></p>'  # noqa E501
#         )
#
#     def players(self, obj: Game):
#         """Players."""
#         return format_html(f'{obj.min_players} &mdash; {obj.max_players}')
#
#     def time(self, obj: Game):
#         """Time."""
#         return format_html(f'{obj.min_play_time} &mdash; {obj.max_play_time}')
#
#
# @admin.register(Review)
# class ReviewAdmin(admin.ModelAdmin):
#     list_display = ('game', 'player', 'rating', 'reviewed_at')
#     search_fields = ('game__name',)
#     ordering = (F('reviewed_at').desc(nulls_first=True),)
#
#
# @admin.register(Player)
# class PlayerAdmin(admin.ModelAdmin):
#     list_display = ('id', 'nick', 'reviews_cnt', 'name', 'scraped_at', 'rec_at', 'last_review_at')
#     ordering = ['rec_at']
#     search_fields = ('nick',)
#     exclude = ('reviews_cnt', 'reviews_scr')
#     actions = (scrape_player_cmd, predict_player_cmd)
#
#
# @admin.register(Day)
# class DayAdmin(admin.ModelAdmin):
#     list_display = ('id', 'day', 'reviews_cnt', 'reviews_avg')
#     ordering = ('day',)
#
#
# @admin.register(Award)
# class AwardAdmin(admin.ModelAdmin):
#     list_display = ('game', 'type', 'description', 'badge', 'awarded_at', 'score')
#     ordering = ('-awarded_at',)
#
#
# @admin.register(PlayerProxy)
# class PlayerScheduleAdmin(admin.ModelAdmin):
#     list_display = ('id', 'nick', 'redo_requested_at', 'redo_started_at', 'redo_completed_at')
#     search_fields = ('nick',)
#     ordering = ('-redo_requested_at', '-redo_started_at', '-redo_completed_at')


# @admin.action(description='Scrape games shop')
# def scrape_games_shop_cmd(modeladmin, request, queryset):
#     """Scrape games shop command."""
#     logger.info('Admin cmd: scraping games shop')
#     shops = defaultdict(list)
#     for shopgame in queryset:
#         shops[shopgame.shop.name].append(shopgame)
#     for shopgames in shops.values():
#         scrape_site(shopgames[0].shop, shopgames=shopgames)
#
# @retry(OperationalError, delay=3, jitter=3, max_delay=30)
# def mark_mia_view(request, game_id, shop_id):
#     """Mark game MIA."""
#     shopgame, _ = ShopGame.objects.update_or_create(
#         game_id=game_id,
#         shop_id=shop_id,
#         defaults={
#             'url_at': now(),
#             'url': None,
#             'mia': True,
#         },
#     )
#     shop_name = shopgame.shop.name.lower().replace(' ', '')
#     if shop_name.startswith('meeps'):
#         shop_name = 'mav'
#     elif shop_name.startswith('grinning'):
#         shop_name = 'gargoyle'
#     back_url = reverse(f'admin:main_shopgame{shop_name.lower()}_changelist')
#     return redirect(back_url)
#
#
