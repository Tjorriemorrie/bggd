import logging
from collections import defaultdict
from datetime import timedelta

from django.contrib import admin
from django.db import OperationalError, models
from django.db.models import ExpressionWrapper, F, Min, QuerySet
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.timezone import now
from retry import retry

from main.constants import (
    SHOP_GARGOYLE,
    SHOP_GEEKHOME,
    SHOP_LEVEL_UP,
    SHOP_MEEPS_AND_VEEPS,
    SHOP_SWORD_AND_BOARD,
    SHOP_THD,
    SHOP_TIMELESS,
    SHOP_TTG,
)
from main.forms import ShopGameForm
from main.models import Award, Day, Game, Label, Player, PlayerProxy, Price, Review, Shop, ShopGame
from main.recommendations import predict_player
from main.scraper import scrape_game, scrape_player
from main.shops import scrape_site, update_game_shop_prices

logger = logging.getLogger(__name__)


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ['bgg_id', 'name', 'type']
    list_filter = ['type']
    ordering = ['type', 'name']


@admin.action(description='Scrape games')
def scrape_game_cmd(modeladmin, request, queryset):
    """Scrape game command."""
    for obj in queryset:
        scrape_game(obj)


@admin.action(description='Scrape players')
def scrape_player_cmd(modeladmin, request, queryset):
    """Scrape player command."""
    for obj in queryset:
        scrape_player(obj)


@admin.action(description='Predict players')
def predict_player_cmd(modeladmin, request, queryset):
    """Predict player command."""
    game_ids = Game.objects.values_list('id', flat=True)
    for obj in queryset:
        predict_player(obj, game_ids)


@admin.action(description='Update shop game prices')
def update_game_shop_prices_cmd(modeladmin, request, queryset):
    """Update game shop prices command."""
    games = set([g for g in queryset])
    for game in games:
        update_game_shop_prices(game)


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'hotness',
        'rank',
        'title',
        'year',
        'min_age',
        'players',
        'time',
        'reviews_cnt_fmt',
        'scraped_at',
        'bgg_id',
        'shop_price',
        'shop_updated_at',
    )
    # list_filter = ('shop_available',)
    ordering = ('-hotness',)
    actions = (scrape_game_cmd, update_game_shop_prices_cmd)
    search_fields = ('name',)
    exclude = ('shop_available', 'shop_price', 'shop_saving', 'hotness', 'sim_cluster')

    def reviews_cnt_fmt(self, obj: Game):
        """Format reviews count."""
        url = reverse('admin:main_review_changelist')
        return format_html(f'<a href="{url}?game={obj.pk}">{obj.reviews_cnt}</a>')

    def title(self, obj: Game):
        """Title."""
        return format_html(
            f'<p><span style="float:left; min-width:100px"><img height="50" src="{obj.img}"/></span>{obj.name}<br/><small>{obj.pitch}</small></p>'  # noqa E501
        )

    def players(self, obj: Game):
        """Players."""
        return format_html(f'{obj.min_players} &mdash; {obj.max_players}')

    def time(self, obj: Game):
        """Time."""
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
class DayAdmin(admin.ModelAdmin):
    list_display = ('id', 'day', 'reviews_cnt', 'reviews_avg')
    ordering = ('day',)


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = ('game', 'type', 'description', 'badge', 'awarded_at', 'score')
    ordering = ('-awarded_at',)


@admin.register(PlayerProxy)
class PlayerScheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'nick', 'redo_requested_at', 'redo_started_at', 'redo_completed_at')
    search_fields = ('nick',)
    ordering = ('-redo_requested_at', '-redo_started_at', '-redo_completed_at')


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'host')


@admin.action(description='Scrape games shop')
def scrape_games_shop_cmd(modeladmin, request, queryset):
    """Scrape games shop command."""
    logger.info('Admin cmd: scraping games shop')
    shops = defaultdict(list)
    for shopgame in queryset:
        shops[shopgame.shop.name].append(shopgame)
    for shopgames in shops.values():
        scrape_site(shopgames[0].shop, shopgames=shopgames)


@admin.register(ShopGame)
class ShopGameAdmin(admin.ModelAdmin):
    actions = (scrape_games_shop_cmd,)
    list_display = [
        'shop',
        'game',
        'mia',
        'prices_cnt',
        'current_available',
        'current_price',
        'url_at',
        'url',
    ]
    fields = ['shop', 'game', 'url', 'mia']
    search_fields = ['game__name', 'url']
    list_filter = ['shop__name', 'mia']
    # ordering = [F('mean_saving').desc(nulls_last=True), '-updated_at']
    ordering = ['url_at']
    form = ShopGameForm

    # def save_model(self, request, obj, form, change):
    #     """Save model."""
    #     if obj.url:
    #         obj.url = obj.url.partition('?')[0]
    #     obj.url_at = now()
    #     super().save_model(request, obj, form, change)

    def _response_post_save(self, request, obj):  # noqa PLR0911
        """Response post save."""
        if obj.shop.name == SHOP_MEEPS_AND_VEEPS:
            return redirect('/admin/main/shopgamemav/')
        elif obj.shop.name == SHOP_TIMELESS:
            return redirect('/admin/main/shopgametimeless/')
        elif obj.shop.name == SHOP_GEEKHOME:
            return redirect('/admin/main/shopgamegeekhome/')
        elif obj.shop.name == SHOP_THD:
            return redirect('/admin/main/shopgamethehiddenden/')
        elif obj.shop.name == SHOP_TTG:
            return redirect('/admin/main/shopgametabletopguru/')
        elif obj.shop.name == SHOP_GARGOYLE:
            return redirect('/admin/main/shopgamegargoyle/')
        elif obj.shop.name == SHOP_LEVEL_UP:
            return redirect('/admin/main/shopgamelevelup/')
        elif obj.shop.name == SHOP_SWORD_AND_BOARD:
            return redirect('/admin/main/shopgameswordandboard/')
        else:
            return super()._response_post_save(request, obj)

    def prices_cnt(self, obj: ShopGame) -> str:
        """Prices count."""
        return f'{obj.prices.count()}'


@admin.action(description='Mark shop games as updated')
def shopgames_updated_at_cmd(modeladmin, request, queryset):
    """Shopgames updated at command."""
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
    list_display = [
        'title',
        'year',
        'tl_shop',
        'ttg_shop',
        'gg_shop',
        'thd_shop',
        'mav_shop',
        'gh_shop',
        'sab_shop',
        'lu_shop',
        'priority',
        'oldest_updated_at',
        'created_at',
    ]
    search_fields = ('name',)
    actions = [shopgames_updated_at_cmd]

    @admin.display(ordering=F('name'))
    def title(self, game: Game):
        """Title."""
        return format_html(f'<p>{game.name}<br/><img height="60" src="{game.img}"/></p>')

    @admin.display(ordering=F('priority').desc(nulls_first=True))
    def priority(self, game: Game) -> str:
        """Priority."""
        return f'{int(game.priority * 1000)}'

    @admin.display(ordering=F('oldest_updated_at').asc(nulls_first=True))
    def oldest_updated_at(self, game: Game) -> str:
        """Oldest updated at."""
        old = f'{game.oldest_updated_at:%Y-%m-%d %H:%I}' if game.oldest_updated_at else ''
        return f'{old}'

    def get_queryset(self, request) -> QuerySet:
        """Get query."""
        qs = self.model._default_manager.get_queryset()
        qs = qs.filter(scraped_at__isnull=False)
        one_month = now() - timedelta(days=30)
        qs = qs.filter(created_at__lt=one_month)
        qs = qs.annotate(oldest_updated_at=Min('shopgames__updated_at'))
        qs = qs.annotate(
            now_till_up=ExpressionWrapper(now() - F('oldest_updated_at'), models.FloatField())
        )
        qs = qs.annotate(
            up_till_cr=ExpressionWrapper(
                F('oldest_updated_at') - F('created_at'), models.FloatField()
            )
        )
        qs = qs.annotate(
            priority=ExpressionWrapper(
                (F('now_till_up') * 1.0) / (F('up_till_cr') * 1.0), models.FloatField()
            )
        )
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    @admin.display()
    def tl_shop(self, game: Game):
        """Show shop."""
        shop = Shop.objects.get(name=SHOP_TIMELESS)
        return self.format_shop(game, shop)

    @admin.display()
    def mav_shop(self, game: Game):
        """Show shop."""
        shop = Shop.objects.get(name=SHOP_MEEPS_AND_VEEPS)
        return self.format_shop(game, shop)

    @admin.display()
    def gg_shop(self, game: Game):
        """Show shop."""
        shop = Shop.objects.get(name=SHOP_GARGOYLE)
        return self.format_shop(game, shop)

    @admin.display()
    def thd_shop(self, game: Game):
        """Show shop."""
        shop = Shop.objects.get(name=SHOP_THD)
        return self.format_shop(game, shop)

    @admin.display()
    def ttg_shop(self, game: Game):
        """Show shop."""
        shop = Shop.objects.get(name=SHOP_TTG)
        return self.format_shop(game, shop)

    @admin.display()
    def gh_shop(self, game: Game):
        """Show shop."""
        shop = Shop.objects.get(name=SHOP_GEEKHOME)
        return self.format_shop(game, shop)

    @admin.display()
    def sab_shop(self, game: Game):
        """Show shop."""
        shop = Shop.objects.get(name=SHOP_SWORD_AND_BOARD)
        return self.format_shop(game, shop)

    @admin.display()
    def lu_shop(self, game: Game):
        """Show shop."""
        shop = Shop.objects.get(name=SHOP_LEVEL_UP)
        return self.format_shop(game, shop)

    def format_shop(self, game: Game, shop: Shop) -> str:
        """Format shop."""
        shopgame = ShopGame.objects.filter(game=game, shop=shop).first()
        top_tag = f'<a href="{shop.get_search_url(game)}" target="_blank">search</a>'

        if not shopgame:
            status = 'no shop'
            shopgame_url = f'<a href="/admin/main/shopgame/add/?shop={shop.id}&game={game.id}" target="_blank">add url</a>'  # noqa E501

        else:
            shopgame_url = (
                f'<a href="/admin/main/shopgame/{shopgame.pk}/change" target="_blank">edit url</a>'
            )
            if shopgame.mia:
                status = '<img src="/static/admin/img/icon-no.svg" alt="False">'

            else:
                top_tag = f'<a href="{shopgame.url}" target="_blank">go game</a>'
                if not shopgame.current_price:
                    status = 'no price'

                elif not shopgame.current_available:
                    status = 'no stock'

                else:
                    status = f'R{shopgame.current_price}'

        return format_html(f'{top_tag}<br/>' f'{shopgame_url}<br/>' f'{status}')


@admin.action(description='Mark The Hidden Den shopgames as MIA')
def mark_mia_thd_cmd(modeladmin, request, queryset):
    """Mark THD MIA command."""
    shop = Shop.objects.get(name=SHOP_THD)
    for game in queryset:
        shopgame, _ = ShopGame.objects.update_or_create(
            game=game,
            shop=shop,
            defaults={
                'url_at': now(),
                'url': None,
                'mia': True,
            },
        )


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
        """Get MaV query."""
        return Game.objects.exclude(shopgames__shop__name=SHOP_MEEPS_AND_VEEPS)

    def title(self, obj: Game):
        """MaV title."""
        return format_html(f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def mav(self, obj: Game):
        """Meeps and Veeps."""
        mav = Shop.objects.get(name=SHOP_MEEPS_AND_VEEPS)
        search_url = mav.get_search_url(obj)
        shopgame_mia_url = reverse(
            'admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': mav.id}
        )
        return format_html(
            f'<a href="{search_url}" target="_blank">search MaV</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={mav.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        """Format hotness."""
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
        """Get timeless query."""
        return Game.objects.exclude(shopgames__shop__name=SHOP_TIMELESS)

    def title(self, obj: Game):
        """Timeless title."""
        return format_html(f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def timeless(self, obj: Game):
        """Timeless."""
        timeless = Shop.objects.get(name=SHOP_TIMELESS)
        search_url = timeless.get_search_url(obj)
        shopgame_mia_url = reverse(
            'admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': timeless.id}
        )
        return format_html(
            f'<a href="{search_url}" target="_blank">search timeless</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={timeless.id}&game={obj.id}">add url</a><br/><br/>'  # noqa E501
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        """Format hotness."""
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
        """Get Geekhome query."""
        return Game.objects.exclude(shopgames__shop__name=SHOP_GEEKHOME)

    def title(self, obj: Game):
        """Geekhome title."""
        return format_html(f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def geekhome(self, obj: Game):
        """Geekhome."""
        gh = Shop.objects.get(name=SHOP_GEEKHOME)
        search_url = gh.get_search_url(obj)
        shopgame_mia_url = reverse(
            'admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': gh.id}
        )
        return format_html(
            f'<a href="{search_url}" target="_blank">search geekhome</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={gh.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        """Format hotness."""
        hotness = int(obj.hotness) if obj.hotness else 0
        return format_html(f'{hotness}')


class ShopGameTheHiddenDen(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop The Hidden Den'
        verbose_name_plural = 'Shop The Hidden Den'


@admin.register(ShopGameTheHiddenDen)
class ShopGameTheHiddenDenAdmin(admin.ModelAdmin):
    list_display = ('thd', 'title', 'year', 'hotness_fmt')
    ordering = ('year', 'hotness')
    actions = (mark_mia_thd_cmd,)

    def get_queryset(self, request):
        """Get THD query."""
        return Game.objects.exclude(shopgames__shop__name=SHOP_THD)

    def title(self, obj: Game):
        """THD title."""
        return format_html(f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def thd(self, obj: Game):
        """The Hidden Den."""
        thd = Shop.objects.get(name=SHOP_THD)
        search_url = thd.get_search_url(obj)
        shopgame_mia_url = reverse(
            'admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': thd.id}
        )
        return format_html(
            f'<a href="{search_url}" target="_blank">search {thd}</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={thd.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        """Format hotness."""
        hotness = int(obj.hotness) if obj.hotness else 0
        return format_html(f'{hotness}')


class ShopGameTabletopGuru(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop Tabletop Guru'
        verbose_name_plural = 'Shop Tabletop Guru'


@admin.action(description='Mark Tabletop guru shopgames as MIA')
def mark_mia_ttg_cmd(modeladmin, request, queryset):
    """Mark TTG MIA command."""
    shop = Shop.objects.get(name=SHOP_TTG)
    for game in queryset:
        shopgame, _ = ShopGame.objects.update_or_create(
            game=game,
            shop=shop,
            defaults={
                'url_at': now(),
                'url': None,
                'mia': True,
            },
        )


@admin.register(ShopGameTabletopGuru)
class ShopGameTabletopGuruAdmin(admin.ModelAdmin):
    list_display = ('ttg', 'title', 'year', 'hotness_fmt')
    ordering = ('year', 'hotness')
    actions = (mark_mia_ttg_cmd,)

    def get_queryset(self, request):
        """Get TTG query."""
        return Game.objects.exclude(shopgames__shop__name=SHOP_TTG)

    def title(self, obj: Game):
        """TTG title."""
        return format_html(f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def ttg(self, obj: Game):
        """Table top guru."""
        ttg = Shop.objects.get(name=SHOP_TTG)
        search_url = ttg.get_search_url(obj)
        shopgame_mia_url = reverse(
            'admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': ttg.id}
        )
        return format_html(
            f'<a href="{search_url}" target="_blank">search {ttg}</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={ttg.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        """Format hotness."""
        hotness = int(obj.hotness) if obj.hotness else 0
        return format_html(f'{hotness}')


class ShopGameGargoyle(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop Grinning Gargoyle'
        verbose_name_plural = 'Shop Grinning Gargoyle'


@admin.action(description='Mark Grinning Gargoyle shopgames as MIA')
def mark_mia_gargoyle_cmd(modeladmin, request, queryset):
    """Mark gargoyle MIA command."""
    shop = Shop.objects.get(name=SHOP_GARGOYLE)
    for game in queryset:
        shopgame, _ = ShopGame.objects.update_or_create(
            game=game,
            shop=shop,
            defaults={
                'url_at': now(),
                'url': None,
                'mia': True,
            },
        )


@admin.register(ShopGameGargoyle)
class ShopGameGargoyleAdmin(admin.ModelAdmin):
    list_display = ('gargoyle', 'title', 'year', 'hotness_fmt')
    ordering = ('year', 'hotness')
    actions = (mark_mia_gargoyle_cmd,)

    def get_queryset(self, request):
        """Get gargoyle query."""
        return Game.objects.exclude(shopgames__shop__name=SHOP_GARGOYLE)

    def title(self, obj: Game):
        """Title property."""
        return format_html(f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def gargoyle(self, obj: Game):
        """Gargoyle shop."""
        gar = Shop.objects.get(name=SHOP_GARGOYLE)
        search_url = gar.get_search_url(obj)
        shopgame_mia_url = reverse(
            'admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': gar.id}
        )
        return format_html(
            f'<a href="{search_url}" target="_blank">search {gar}</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={gar.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        """Format hotness."""
        hotness = int(obj.hotness) if obj.hotness else 0
        return format_html(f'{hotness}')


class ShopGameSwordAndBoard(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop Sword and Board'
        verbose_name_plural = 'Shop Sword and Board'


@admin.action(description='Mark Sword and Board shopgames as MIA')
def mark_mia_sword_and_board_cmd(modeladmin, request, queryset):
    """Mark sword and board MIA command."""
    shop = Shop.objects.get(name=SHOP_SWORD_AND_BOARD)
    for game in queryset:
        shopgame, _ = ShopGame.objects.update_or_create(
            game=game,
            shop=shop,
            defaults={
                'url_at': now(),
                'url': None,
                'mia': True,
            },
        )


@admin.register(ShopGameSwordAndBoard)
class ShopGameSwordAndBoardAdmin(admin.ModelAdmin):
    list_display = ('sab', 'title', 'year', 'hotness_fmt')
    ordering = ('year', 'hotness')
    actions = (mark_mia_sword_and_board_cmd,)

    def get_queryset(self, request):
        """Get sword and board query."""
        return Game.objects.exclude(shopgames__shop__name=SHOP_SWORD_AND_BOARD)

    def title(self, obj: Game):
        """Title property."""
        return format_html(f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def sab(self, obj: Game):
        """Sword and board shop."""
        sab = Shop.objects.get(name=SHOP_SWORD_AND_BOARD)
        search_url = sab.get_search_url(obj)
        shopgame_mia_url = reverse(
            'admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': sab.id}
        )
        return format_html(
            f'<a href="{search_url}" target="_blank">search {sab}</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={sab.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        """Format hotness."""
        hotness = int(obj.hotness) if obj.hotness else 0
        return format_html(f'{hotness}')


class ShopGameLevelUp(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop Level Up'
        verbose_name_plural = 'Shop Level Up'


@admin.action(description='Mark Level Up shopgames as MIA')
def mark_mia_level_up_cmd(modeladmin, request, queryset):
    """Mark level up MIA command."""
    shop = Shop.objects.get(name=SHOP_LEVEL_UP)
    for game in queryset:
        shopgame, _ = ShopGame.objects.update_or_create(
            game=game,
            shop=shop,
            defaults={
                'url_at': now(),
                'url': None,
                'mia': True,
            },
        )


@admin.register(ShopGameLevelUp)
class ShopGameLevelUpAdmin(admin.ModelAdmin):
    list_display = ('lu', 'title', 'year', 'hotness_fmt')
    ordering = ('year', 'hotness')
    actions = (mark_mia_level_up_cmd,)

    def get_queryset(self, request):
        """Get level up query."""
        return Game.objects.exclude(shopgames__shop__name=SHOP_LEVEL_UP)

    def title(self, obj: Game):
        """Title property."""
        return format_html(f'<p>{obj.name}<br/><img height="100" src="{obj.img}"/></p>')

    def lu(self, obj: Game):
        """Level up shop."""
        lu = Shop.objects.get(name=SHOP_LEVEL_UP)
        search_url = lu.get_search_url(obj)
        shopgame_mia_url = reverse(
            'admin:shopgame_mia', kwargs={'game_id': obj.id, 'shop_id': lu.id}
        )
        return format_html(
            f'<a href="{search_url}" target="_blank">search {lu}</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={lu.id}&game={obj.id}">add url</a><br/><br/>'
            f'<a href="{shopgame_mia_url}">mark as MIA</a>'
        )

    def hotness_fmt(self, obj: Game):
        """Format hotness."""
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
    """Mark game MIA."""
    shopgame, _ = ShopGame.objects.update_or_create(
        game_id=game_id,
        shop_id=shop_id,
        defaults={
            'url_at': now(),
            'url': None,
            'mia': True,
        },
    )
    shop_name = shopgame.shop.name.lower().replace(' ', '')
    if shop_name.startswith('meeps'):
        shop_name = 'mav'
    elif shop_name.startswith('grinning'):
        shop_name = 'gargoyle'
    back_url = reverse(f'admin:main_shopgame{shop_name.lower()}_changelist')
    return redirect(back_url)


admin_site_urls = admin.site.urls
admin_site_urls[0].insert(
    7, path('game/<int:game_id>/shop/<int:shop_id>/mia/', mark_mia_view, name='shopgame_mia')
)
