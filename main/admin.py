import re

from django.contrib import admin
from django.db.models import F
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timezone import now

from main.constants import SHOP_RARU
from main.models import Game, Review, Player, Day, Award, PlayerProxy, Shop, ShopGame, Price
from main.recommendations import predict_player
from main.scraper import scrape_game, scrape_player
from main.shops import scrape_raru


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


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'hotness', 'rank', 'title', 'year', 'min_age', 'players', 'time', 'reviews_cnt_fmt', 'scraped_at', 'bgg_id', 'shop_price')
    # list_filter = ('shop_available',)
    ordering = ('-hotness',)
    actions = (scrape_game_cmd,)
    search_fields = ('name',)
    exclude = ('shop_available', 'shop_price', 'shop_saving', 'hotness', 'mechanic_cluster')

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
    list_display = ('id', 'nick', 'reviews_cnt', 'name', 'scraped_at', 'rec_at')
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
    scrape_raru(queryset)


@admin.register(ShopGame)
class ShopGameAdmin(admin.ModelAdmin):
    actions = (scrape_games_shop_cmd,)
    list_display = ['shop', 'game', 'current_price', 'mean_price', 'min_price', 'max_price', 'mean_saving',  'mia']
    fields = ['shop', 'game', 'url', 'mia']
    search_fields = ['game__name', 'url']
    list_filter = ['shop__name']
    ordering = [F('mean_saving').desc(nulls_last=True), '-updated_at']

    def save_model(self, request, obj, form, change):
        obj.url_at = now()
        super().save_model(request, obj, form, change)

    def _response_post_save(self, request, obj):
        if obj.shop.name == SHOP_RARU:
            return redirect('/admin/main/shopgameraru/')
        else:
            return super().response_post_save_change(request, obj)


class ShopGameRaru(Game):
    class Meta:
        proxy = True
        verbose_name = 'Shop Raru'
        verbose_name_plural = 'Shop Raru'


@admin.register(ShopGameRaru)
class ShopGameRaruAdmin(admin.ModelAdmin):
    list_display = ('raru', 'title', 'year', 'hotness_fmt')
    ordering = ('hotness', 'year')

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
        return format_html(
            f'<a href="{raru_search}" target="_blank">search raru</a><br/><br/>'
            f'<a href="/admin/main/shopgame/add/?shop={raru.id}&game={obj.id}">add url</a>')

    def hotness_fmt(self, obj: Game):
        hotness = int(obj.hotness) if obj.hotness else 0
        return format_html(f'{hotness}')


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ['shopgame', 'day', 'status', 'price']
