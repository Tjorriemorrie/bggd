import logging
import re
from collections import defaultdict

from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db import OperationalError, models
from django.db.models import F, QuerySet, Min, ExpressionWrapper
from django.shortcuts import redirect
from django.urls import reverse, path
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from retry import retry

from main.constants import SHOP_RARU, SHOP_TAKEALOT, SHOP_MEEPS_AND_VEEPS, \
    SHOP_TIMELESS, SHOP_GEEKHOME
from main.models import Game, Review, Player, Day, Award, PlayerProxy, Shop, \
    ShopGame, Price, Label
from main.recommendations import predict_player
from main.scraper import scrape_game, scrape_player
from main.shops import scrape_raru, scrape_timeless, scrape_meeps_and_veeps, scrape_geekhome, update_game_shop_prices

logger = logging.getLogger(__name__)


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ['bgg_id', 'name', 'type']
    list_filter = ['type']
    ordering = ['type', 'name']


@admin.action(description='Scrape games')
def scrape_game_cmd(modeladmin, request, queryset):
    for obj in queryset:
        scrape_game(obj)


@admin.action(description='Scrape players')
def scrape_player_cmd(modeladmin, request, queryset):
    for obj in queryset:
        scrape_player(obj)


@admin.action(description='Predict players')
def predict_player_cmd(modeladmin, request, queryset):
    game_ids = Game.objects.values_list('id', flat=True)
    for obj in queryset:
        predict_player(obj, game_ids)


@admin.action(description='Update shop game prices')
def update_game_shop_prices_cmd(modeladmin, request, queryset):
    games = set([g for g in queryset])
    for game in games:
        update_game_shop_prices(game)


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'hotness', 'rank', 'title', 'year', 'min_age', 'players', 'time', 'reviews_cnt_fmt', 'scraped_at', 'bgg_id', 'shop_price', 'shop_updated_at')
    # list_filter = ('shop_available',)
    ordering = ('-hotness',)
    actions = (scrape_game_cmd, update_game_shop_prices_cmd)
    search_fields = ('name',)
    exclude = ('shop_available', 'shop_price', 'shop_saving', 'hotness', 'sim_cluster')

    def reviews_cnt_fmt(self, obj: Game):
        url = reverse('admin:main_review_changelist')
        return format_html(f'<a href="{url}?game={obj.pk}">{obj.reviews_cnt}</a>')

    def title(self, obj: Game):
        return format_html(
            f'<p><span style="float:left; min-width:100px"><img height="50" src="{obj.img}"/></span>{obj.name}<br/><small>{obj.pitch}</small></p>')

    def players(self, obj: Game):
        return format_html(f'{obj.min_players} &mdash; {obj.max_players}')

    def time(self, obj: Game):
        return format_html(f'{obj.min_play_time} &mdash; {obj.max_play_time}')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('game', 'player', 'rating', 'reviewed_at')
    search_fields = ('game__name',)
    ordering = (F('reviewed_at').desc(nulls_first=True),)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'nick', 'reviews_cnt', 'name', 'scraped_at', 'rec_at', 'last_review_at')
    ordering = ['rec_at']
    search_fields = ('nick',)
    exclude = ('reviews_cnt', 'reviews_scr')
    actions = (scrape_player_cmd, predict_player_cmd)


@admin.register(Day)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'day', 'reviews_cnt', 'reviews_avg')
    ordering = ('day',)


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = ('game', 'type', 'description', 'badge', 'awarded_at', 'score')
    ordering = ('-awarded_at',)


@admin.register(PlayerProxy)
class PlayerScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'nick', 'redo_requested_at', 'redo_started_at', 'redo_completed_at')
    search_fields = ('nick',)
    ordering = ('-redo_requested_at', '-redo_started_at', '-redo_completed_at')


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    pass


@admin.action(description='Scrape games shop')
def scrape_games_shop_cmd(modeladmin, request, queryset):
    logger.info('Admin cmd: scraping games shop')
    shops = defaultdict(list)
    for shopgame in queryset:
        shops[shopgame.shop.name].append(shopgame)
    for name, shopgames in shops.items():
        if name == SHOP_RARU:
            scrape_raru(shopgames)
        elif name == SHOP_MEEPS_AND_VEEPS:
            scrape_meeps_and_veeps(shopgames)
        elif name == SHOP_TIMELESS:
            scrape_timeless(shopgames)
        elif name == SHOP_GEEKHOME:
            scrape_geekhome(shopgames)
        else:
            raise ValueError(f'Unexpected shop: {name}')


@admin.register(ShopGame)
class ShopGameAdmin(admin.ModelAdmin):
    actions = (scrape_games_shop_cmd,)
    list_display = [
        'shop', 'game', 'mia', 'prices_cnt', 'url_at']
    fields = ['shop', 'game', 'url', 'mia']
    search_fields = ['game__name', 'url']
    list_filter = ['shop__name', 'mia']
    # ordering = [F('mean_saving').desc(nulls_last=True), '-updated_at']
    ordering = ['url_at']

    def save_model(self, request, obj, form, change):
        if obj.url:
            obj.url = obj.url.partition('?')[0]
        obj.url_at = now()
        super().save_model(request, obj, form, change)

    def _response_post_save(self, request, obj):
        if obj.shop.name == SHOP_RARU:
            return redirect('/admin/main/shopgameraru/')
        elif obj.shop.name == SHOP_MEEPS_AND_VEEPS:
            return redirect('/admin/main/shopgamemav/')
        elif obj.shop.name == SHOP_TIMELESS:
            return redirect('/admin/main/shopgametimeless/')
        elif obj.shop.name == SHOP_GEEKHOME:
            return redirect('/admin/main/shopgamegeekhome/')
        else:
            return super()._response_post_save(request, obj)

    def prices_cnt(self, obj: ShopGame) -> str:
        return f'{obj.prices.count()}'


@admin.action(description='Mark shop games as updated')
def shopgames_updated_at_cmd(modeladmin, request, queryset):
    logger.info('Marking shopgames as updated')
    games = set(g for g in queryset)
    for game in games:
        for shopgame in game.shopgames.all():
            shopgame.updated_at = now()
            shopgame.save()


class ShopGameRenew(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop Renew'
        verbose_name_plural = 'Shop Renews'


@admin.register(ShopGameRenew)
class ShopGameRenewAdmin(admin.ModelAdmin):
    list_display = ['name', 'year', 'mav_shop', 'raru_shop', 'tl_shop', 'gh_shop', 'priority', 'oldest_updated_at']
    actions = [shopgames_updated_at_cmd]

    @admin.display(ordering=F('priority').desc(nulls_last=False))
    def priority(self, game: Game) -> str:
        return f'{int(game.priority * 1000)}'

    @admin.display(ordering=F('oldest_updated_at').asc(nulls_last=False))
    def oldest_updated_at(self, game: Game) -> str:
        old = f'{game.oldest_updated_at:%Y-%m-%d %H:%I}' if game.oldest_updated_at else ''
        return f'{old}'

    def get_queryset(self, request) -> QuerySet:
        qs = self.model._default_manager.get_queryset()
        qs = qs.filter(scraped_at__isnull=False)
        qs = qs.annotate(oldest_updated_at=Min('shopgames__updated_at'))
        qs = qs.annotate(now_till_up=ExpressionWrapper(now() - F('oldest_updated_at'), models.FloatField()))
        qs = qs.annotate(up_till_cr=ExpressionWrapper(F('oldest_updated_at') - F('created_at'), models.FloatField()))
        qs = qs.annotate(priority=ExpressionWrapper((F('now_till_up') * 1.0) / (F('up_till_cr') * 1.0), models.FloatField()))
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    @admin.display()
    def mav_shop(self, game: Game) -> str:
        mav = Shop.objects.get(name=SHOP_MEEPS_AND_VEEPS)

        # search
        name = game.name.replace(':', '').replace('?', ' ').replace(',', '').replace('!', ' ').replace('&', '')
        mav_search = f'https://meepsandveeps.co.za/search?type=product&q={name}'
        # shopgame_mia_url = reverse('admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': mav.id})

        shopgame = ShopGame.objects.filter(game=game, shop=mav).first()
        if not shopgame:
            status = 'no shop'
        elif shopgame.mia:
            status = '<img src="/static/admin/img/icon-no.svg" alt="False">'
        elif not shopgame.current_price:
            status = 'no price'
        else:
            status = f'R{shopgame.current_price}'

        return format_html(
            f'<a href="{mav_search}" target="_blank">search</a><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={mav.id}&game={game.id}">add url</a><br/>'
            f'{status}'
            # f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    @admin.display()
    def raru_shop(self, game: Game) -> str:
        raru = Shop.objects.get(name=SHOP_RARU)

        # search
        words = re.findall('(\w+)', game.name)
        words.sort(key=len, reverse=True)
        words = [w for w in words if w.lower() not in ['edition', 'board', 'game']]
        words = [f"{w}'s" if f"{w}'s" in game.name else w for w in words if w != 's']
        words = [f"{w}'t" if f"{w}'t" in game.name else w for w in words if w != 't']
        raru_search = 'https://raru.co.za/boards-dice/search/' + '+'.join(words[:3])
        # shopgame_mia_url = reverse('admin:shopgame_mia', kwargs={'game_id': game.id, 'shop_id': raru.id})

        shopgame = ShopGame.objects.filter(game=game, shop=raru).first()
        if not shopgame:
            status = 'no shop'
        elif shopgame.mia:
            status = '<img src="/static/admin/img/icon-no.svg" alt="False">'
        elif not shopgame.current_price:
            status = 'no price'
        else:
            status = f'R{shopgame.current_price}'

        return format_html(
            f'<a href="{raru_search}" target="_blank">search</a><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={raru.id}&game={game.id}">add url</a><br/>'
            f'{status}'
            # f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    @admin.display()
    def tl_shop(self, game: Game) -> str:
        tl = Shop.objects.get(name=SHOP_TIMELESS)

        # search
        name = game.name.replace("'s", '').replace("'t", '').replace("'", '')
        params = urlencode({
            'filter': '',
            'filter_product_name': name,
        })
        timeless_search = f'https://www.timelessboardgames.co.za/online-shop/?{params}'
        # shopgame_mia_url = reverse('admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': timeless.id})

        # status
        shopgame = ShopGame.objects.filter(game=game, shop=tl).first()
        if not shopgame:
            status = 'no shop'
        elif shopgame.mia:
            status = '<img src="/static/admin/img/icon-no.svg" alt="False">'
        elif not shopgame.current_price:
            status = 'no price'
        else:
            status = f'R{shopgame.current_price}'

        return format_html(
            f'<a href="{timeless_search}" target="_blank">search</a><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={tl.id}&game={game.id}">add url</a><br/>'
            f'{status}'
            # f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    @admin.display()
    def gh_shop(self, game: Game) -> str:
        gh = Shop.objects.get(name=SHOP_GEEKHOME)

        # search
        name = game.name  #.replace("'s", '').replace("'t", '').replace("'", '')
        params = urlencode({
            'post_type': 'product',
            's': name,
        })
        gh_search = f'{gh.host}?{params}'
        # shopgame_mia_url = reverse('admin:shopgame_mia', kwargs={'game_id': game.id, 'shop_id': gh.id})

        # status
        shopgame = ShopGame.objects.filter(game=game, shop=gh).first()
        if not shopgame:
            status = 'no shop'
        elif shopgame.mia:
            status = '<img src="/static/admin/img/icon-no.svg" alt="False">'
        elif not shopgame.current_price:
            status = 'no price'
        else:
            status = f'R{shopgame.current_price}'

        return format_html(
            f'<a href="{gh_search}" target="_blank">search</a><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={gh.id}&game={game.id}">add url</a><br/>'
            f'{status}'
            # f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )


class ShopGameRaru(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop Raru'
        verbose_name_plural = 'Shop Raru'


@admin.register(ShopGameRaru)
class ShopGameRaruAdmin(admin.ModelAdmin):
    list_display = ('raru', 'title', 'year', 'hotness_fmt')
    ordering = ('year', 'hotness')

    def get_queryset(self, request):
        return Game.objects.exclude(shopgames__shop__name=SHOP_RARU)

    def title(self, obj: Game):
        return format_html(
            f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def raru(self, obj: Game):
        raru = Shop.objects.get(name=SHOP_RARU)
        words = re.findall('(\w+)', obj.name)
        words.sort(key=len, reverse=True)
        words = [w for w in words if w.lower() not in ['edition', 'board', 'game']]
        words = [f"{w}'s" if f"{w}'s" in obj.name else w for w in words if w != 's']
        words = [f"{w}'t" if f"{w}'t" in obj.name else w for w in words if w != 't']
        raru_search = 'https://raru.co.za/boards-dice/search/' + '+'.join(words[:3])
        shopgame_mia_url = reverse('admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': raru.id})
        return format_html(
            f'<a href="{raru_search}" target="_blank">search raru</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={raru.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>')

    def hotness_fmt(self, obj: Game):
        hotness = int(obj.hotness) if obj.hotness else 0
        return format_html(f'{hotness}')


class ShopGameMav(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop Meeps and Veeps'
        verbose_name_plural = 'Shop Meeps and Veeps'


@admin.register(ShopGameMav)
class ShopGameMavAdmin(admin.ModelAdmin):
    list_display = ('mav', 'title', 'year', 'hotness_fmt')
    ordering = ('year', 'hotness')

    def get_queryset(self, request):
        return Game.objects.exclude(shopgames__shop__name=SHOP_MEEPS_AND_VEEPS)

    def title(self, obj: Game):
        return format_html(
            f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def mav(self, obj: Game):
        mav = Shop.objects.get(name=SHOP_MEEPS_AND_VEEPS)
        name = obj.name.replace(':', '').replace('?', ' ').replace(',', '').replace('!', ' ').replace('&', '')
        mav_search = f'https://meepsandveeps.co.za/search?type=product&q={name}'
        shopgame_mia_url = reverse('admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': mav.id})
        return format_html(
            f'<a href="{mav_search}" target="_blank">search MaV</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={mav.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        hotness = int(obj.hotness) if obj.hotness else 0
        return format_html(f'{hotness}')


class ShopGameTimeless(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop Timeless'
        verbose_name_plural = 'Shop Timeless'


@admin.register(ShopGameTimeless)
class ShopGameTimelessAdmin(admin.ModelAdmin):
    list_display = ('timeless', 'title', 'year', 'hotness_fmt')
    ordering = ('year', 'hotness')

    def get_queryset(self, request):
        return Game.objects.exclude(shopgames__shop__name=SHOP_TIMELESS)

    def title(self, obj: Game):
        return format_html(
            f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def timeless(self, obj: Game):
        timeless = Shop.objects.get(name=SHOP_TIMELESS)
        name = obj.name.replace("'s", '').replace("'t", '').replace("'", '')
        params = urlencode({
            'filter': '',
            'filter_product_name': name,
        })
        timeless_search = f'https://www.timelessboardgames.co.za/online-shop/?{params}'
        shopgame_mia_url = reverse('admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': timeless.id})
        return format_html(
            f'<a href="{timeless_search}" target="_blank">search timeless</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={timeless.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        hotness = int(obj.hotness) if obj.hotness else 0
        return format_html(f'{hotness}')


class ShopGameGeekhome(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop Geekhome'
        verbose_name_plural = 'Shop Geekhome'


@admin.register(ShopGameGeekhome)
class ShopGameGeekhomeAdmin(admin.ModelAdmin):
    list_display = ('geekhome', 'title', 'year', 'hotness_fmt')
    ordering = ('year', 'hotness')

    def get_queryset(self, request):
        return Game.objects.exclude(shopgames__shop__name=SHOP_GEEKHOME)

    def title(self, obj: Game):
        return format_html(
            f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def geekhome(self, obj: Game):
        gh = Shop.objects.get(name=SHOP_GEEKHOME)
        name = obj.name  #.replace("'s", '').replace("'t", '').replace("'", '')
        params = urlencode({
            'post_type': 'product',
            's': name,
        })
        gh_search = f'{gh.host}?{params}'
        shopgame_mia_url = reverse('admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': gh.id})
        return format_html(
            f'<a href="{gh_search}" target="_blank">search geekhome</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={gh.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        hotness = int(obj.hotness) if obj.hotness else 0
        return format_html(f'{hotness}')


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ['shopgame', 'day', 'status', 'price']
    ordering = ['-day']
    search_fields = ['shopgame__game__name']
    list_filter = ['shopgame__shop__name', 'status']


@retry(OperationalError, delay=3, jitter=3, max_delay=30)
def mark_mia_view(request, game_id, shop_id):
    shopgame, _ = ShopGame.objects.update_or_create(
        game_id=game_id,
        shop_id=shop_id,
        defaults={
            'url_at': now(),
            'url': None,
            'mia': True,
        }
    )
    shop_name = shopgame.shop.name
    if shop_name == SHOP_MEEPS_AND_VEEPS:
        shop_name = 'mav'
    back_url = reverse(f'admin:main_shopgame{shop_name.lower()}_changelist')
    return redirect(back_url)


admin_site_urls = admin.site.urls
admin_site_urls[0].insert(7, path('game/<int:game_id>/shop/<int:shop_id>/mia/', mark_mia_view, name='shopgame_mia'))
