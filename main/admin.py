from django.contrib import admin
from django.db.models import F
from django.urls import reverse
from django.utils.html import format_html

from main.models import Game, Review, Player
from main.scraper import scrape_game_details


@admin.action(description='Scrape games')
def scrape_game_cmd(modeladmin, request, queryset):
    for obj in queryset:
        scrape_game_details(obj)


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('rank', 'title', 'year', 'min_age', 'players', 'time', 'reviews_cnt', 'scraped_at', 'bgg_id')
    ordering = ('-year', 'rank')
    actions = (scrape_game_cmd,)

    def reviews_cnt(self, obj: Game):
        url = reverse('admin:main_review_changelist')
        return format_html(f'<a href="{url}?game={obj.pk}">{obj.reviews.count()}</a>')

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
    list_display = ('id', 'name', 'nick')
    search_fields = ('nick',)
