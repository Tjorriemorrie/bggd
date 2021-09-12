from datetime import datetime
from typing import Optional

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.timezone import now


LABEL_CATEGORY = 'category'
LABEL_MECHANIC = 'mechanic'
LABEL_FAMILY = 'family'
LABEL_SUBDOMAIN = 'subdomain'


class Label(models.Model):
    CHOICES_LABELS = (
        (LABEL_CATEGORY, LABEL_CATEGORY),
        (LABEL_MECHANIC, LABEL_MECHANIC),
        (LABEL_FAMILY, LABEL_FAMILY),
        (LABEL_SUBDOMAIN, LABEL_SUBDOMAIN),
    )
    bgg_id = models.PositiveIntegerField()
    name = models.CharField(max_length=256)
    type = models.CharField(max_length=256, choices=CHOICES_LABELS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'<Label-{self.bgg_id} {self.type} {self.name}>'


class Game(models.Model):
    categories = models.ManyToManyField(Label, related_name='cat_games')
    mechanics = models.ManyToManyField(Label, related_name='mec_games')
    families = models.ManyToManyField(Label, related_name='fam_games')
    subdomains = models.ManyToManyField(Label, related_name='dom_games')

    bgg_id = models.PositiveIntegerField(db_index=True)
    name = models.CharField(max_length=250)
    year = models.PositiveIntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(now().year)])
    url = models.CharField(max_length=250)
    rank = models.PositiveIntegerField()

    # details
    scraped_at = models.DateTimeField(null=True)
    img = models.CharField(max_length=250, null=True)
    pitch = models.CharField(max_length=256, null=True)
    description = models.TextField(null=True)
    min_play_time = models.PositiveSmallIntegerField(null=True)
    max_play_time = models.PositiveSmallIntegerField(null=True)
    # age
    min_age = models.PositiveSmallIntegerField(null=True)
    rec_min_age = models.PositiveSmallIntegerField(null=True)
    # players
    min_players = models.PositiveSmallIntegerField(null=True)
    max_players = models.PositiveSmallIntegerField(null=True)
    rec_min_players = models.PositiveSmallIntegerField(null=True)
    rec_max_players = models.PositiveSmallIntegerField(null=True)
    best_min_players = models.PositiveSmallIntegerField(null=True)
    best_max_players = models.PositiveSmallIntegerField(null=True)
    # weight
    weight_avg = models.FloatField(null=True)

    # from reviews
    rating = models.FloatField(null=True)  # scrape cron update
    reviews_cnt = models.IntegerField(null=True)  # scrape cron update
    recs_cnt = models.IntegerField(null=True)  # scrape cron update

    # hotness
    hotness = models.FloatField(null=True)  # update hotness cron

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('rank',)

    def __str__(self) -> str:
        return f'<Game-{self.bgg_id} {self.name} ({self.year})>'

    @property
    def bgg_link(self):
        return f'https://www.boardgamegeek.com/boardgame/{self.bgg_id}'

    def mechanics_comma(self) -> str:
        return ', '.join([m.name for m in self.mechanics.all()])

    def families_comma(self) -> str:
        return ', '.join([f.name for f in self.families.all()])

    def categories_comma(self) -> str:
        return ', '.join([c.name for c in self.categories.all()])

    def players_fmt(self) -> str:
        if self.rec_min_players:
            rec = f'{self.rec_min_players}'
            if self.rec_max_players > self.rec_min_players:
                rec += f' - {self.rec_max_players}'
        elif self.min_players:
            rec = f'{self.min_players}'
            if self.max_players > self.min_players:
                rec += f' - {self.max_players}'
        else:
            rec = ''
        if self.best_min_players:
            best = f'{self.best_min_players}'
            if self.best_max_players > self.best_min_players:
                best += f' - {self.best_max_players}'
            best = f' (best {best})'
        else:
            best = ''
        return rec + best

    def age_fmt(self) -> str:
        if self.rec_min_age:
            return f'{self.rec_min_age}+'
        elif self.min_age:
            return f'{self.min_age}+'
        return ''


class Player(models.Model):
    bgg_id = models.PositiveIntegerField(null=True)
    nick = models.CharField(max_length=256, db_index=True)

    # updated in scrape
    name = models.CharField(max_length=256, null=True)
    country = models.CharField(max_length=150, null=True)
    area = models.CharField(max_length=150, null=True)
    avatar = models.CharField(max_length=256, null=True)
    scraped_at = models.DateTimeField(db_index=True, null=True)

    # updated in predict (joined with scrape)
    reviews_cnt = models.IntegerField(null=True)
    reviews_scr = models.FloatField(null=True)
    game_recs = models.ManyToManyField(Game, related_name='player_recs')
    rec_at = models.DateTimeField(db_index=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        name = f' ({self.name})' if self.name else ''
        return f'Player {self.nick}{name}'

    @property
    def bgg_link(self):
        return f'https://www.boardgamegeek.com/user/{self.nick}'

    def geo(self):
        geo = ''
        if self.country:
            geo = self.country
        if self.area:
            geo += f' {self.area}'
        return geo or ''


class Day(models.Model):
    day = models.DateField(db_index=True)

    reviews_cnt = models.IntegerField()
    reviews_avg = models.FloatField()
    reviews_adj = models.FloatField()
    last_review_id = models.IntegerField()
    last_review_update = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'<Day {self.day:"%y-%m-%d} cnt={self.reviews_cnt} avg={self.reviews_avg}>'


class GameDay(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='gamedays')
    day = models.ForeignKey(Day, on_delete=models.CASCADE, related_name='gamedays')

    reviews_cnt = models.IntegerField()
    reviews_avg = models.FloatField()
    reviews_adj = models.FloatField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'<GameDay game={self.game.name} {self.day.day:"%y-%m-%d"} cnt={self.reviews_cnt} avg={round(self.reviews_avg, 1)}>'


class Review(models.Model):
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name='reviews')
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name='reviews')
    gameday = models.ForeignKey(
        GameDay, null=True, on_delete=models.SET_NULL, related_name='reviews')

    bgg_id = models.PositiveIntegerField(db_index=True)
    rating = models.FloatField(db_index=True)
    comment = models.CharField(max_length=256, null=True)
    reviewed_at = models.DateTimeField(db_index=True)

    predicted = models.FloatField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(db_index=True, auto_now=True)

    class Meta:
        unique_together = ('player', 'game')

    def __str__(self) -> str:
        return f'<Review-{self.bgg_id} {self.rating} {self.game.name} by {self.player.nick}>'

    @property
    def diff(self) -> float:
        if not self.predicted:
            return 0
        return self.rating - self.predicted

    @property
    def day(self) -> datetime:
        return self.reviewed_at.replace(hour=0, minute=0, second=0, microsecond=0)
