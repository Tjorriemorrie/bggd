from django.contrib import admin
from django.db.models import F
from django.urls import reverse
from django.utils.html import format_html

from main.models import Game, Review, Player, Day, Award, PlayerProxy
from main.recommendations import predict_player
from main.scraper import scrape_game, scrape_player


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
    list_display = ('id', 'rank', 'title', 'year', 'min_age', 'players', 'time', 'reviews_cnt_fmt', 'scraped_at', 'bgg_id')
    ordering = ('-year', 'rank')
    actions = (scrape_game_cmd,)
    search_fields = ('name',)

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
