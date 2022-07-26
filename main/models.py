from datetime import datetime
from typing import List, Optional

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.timezone import now
from jsonfield import JSONField

from main.constants import WEIGHT_HEAVY, WEIGHT_MEDIUM, WEIGHT_LIGHT, STOCK_IN, \
    STOCK_OUT, SHOP_RARU, SHOP_TAKEALOT

LABEL_CATEGORY = 'category'
LABEL_MECHANIC = 'mechanic'
LABEL_FAMILY = 'family'
LABEL_SUBDOMAIN = 'subdomain'

AWARD_GAME_OF_THE_MONTH = 'Game of the month'
AWARD_GAME_OF_THE_YEAR = 'Game of the year'

CHOICES_WEIGHTS = (
    (WEIGHT_HEAVY, WEIGHT_HEAVY),
    (WEIGHT_MEDIUM, WEIGHT_MEDIUM),
    (WEIGHT_LIGHT, WEIGHT_LIGHT),
)


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
    categories = models.ManyToManyField(Label, related_name='cat_games', blank=True)
    mechanics = models.ManyToManyField(Label, related_name='mec_games', blank=True)
    families = models.ManyToManyField(Label, related_name='fam_games', blank=True)
    subdomains = models.ManyToManyField(Label, related_name='dom_games', blank=True)

    bgg_id = models.PositiveIntegerField(db_index=True)
    name = models.CharField(max_length=250)
    year = models.IntegerField(
        validators=[MinValueValidator(-2500), MaxValueValidator(now().year + 1)])
    url = models.CharField(max_length=250)
    rank = models.PositiveIntegerField()

    # details
    scraped_at = models.DateTimeField(null=True, blank=True)
    img = models.CharField(max_length=250, null=True, blank=True)
    pitch = models.CharField(max_length=256, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    min_play_time = models.PositiveSmallIntegerField(null=True, blank=True)
    max_play_time = models.PositiveSmallIntegerField(null=True, blank=True)
    # age
    min_age = models.PositiveSmallIntegerField(null=True, blank=True)
    rec_min_age = models.PositiveSmallIntegerField(null=True, blank=True)
    # players
    min_players = models.PositiveSmallIntegerField(null=True, blank=True)
    max_players = models.PositiveSmallIntegerField(null=True, blank=True)
    rec_min_players = models.PositiveSmallIntegerField(null=True, blank=True)
    rec_max_players = models.PositiveSmallIntegerField(null=True, blank=True)
    best_min_players = models.PositiveSmallIntegerField(null=True, blank=True)
    best_max_players = models.PositiveSmallIntegerField(null=True, blank=True)
    # weight
    weight_avg = models.FloatField(null=True)
    weight_tag = models.CharField(max_length=20, null=True, choices=CHOICES_WEIGHTS)

    # from reviews
    rating = models.FloatField(null=True)  # scrape cron update
    reviews_cnt = models.IntegerField(null=True)  # scrape cron update
    recs_cnt = models.IntegerField(null=True)  # scrape cron update

    # hotness
    hotness = models.FloatField(null=True)  # update hotness cron

    # similar
    mechanic_cluster = models.IntegerField(null=True, blank=True)

    # shops aggregate
    shop_available = models.BooleanField(null=True, blank=True)
    shop_price = models.IntegerField(null=True, blank=True)
    shop_saving = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('rank',)

    def __str__(self) -> str:
        return f'{self.name} ({self.year})'

    @property
    def bgg_link(self):
        return f'https://www.boardgamegeek.com/boardgame/{self.bgg_id}'

    def best_shop(self) -> Optional['ShopGame']:
        return self.shopgames.order_by('-mean_saving', 'updated_at').first()

    def comments(self) -> List['Review']:
        return self.reviews.filter(
            comment__isnull=False,
            player__reviews_scr__isnull=False
        ).order_by('-player__reviews_scr')

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

    def awards_fmt(self) -> str:
        badges = []
        for award in self.awards.all():
            if award.type == AWARD_GAME_OF_THE_YEAR:
                bg = 'bg-success text-light'
                trophy = '<i class="bi bi-trophy-fill"></i>'
            else:
                bg = 'bg-light text-muted'
                trophy = '<i class="bi bi-trophy"></i>'
            badges.append(f"""<span class="badge {bg}" title="{award.description}">
                {trophy}
                {award.badge}
            </span>""")
        return ''.join(badges)


class Player(models.Model):
    bgg_id = models.PositiveIntegerField(null=True)
    nick = models.CharField(max_length=256, unique=True)

    # updated in scrape
    name = models.CharField(max_length=256, null=True, blank=True)
    country = models.CharField(max_length=150, null=True, blank=True)
    area = models.CharField(max_length=150, null=True, blank=True)
    avatar = models.CharField(max_length=256, null=True, blank=True)
    scraped_at = models.DateTimeField(db_index=True, null=True, blank=True)

    # updated in predict (joined with scrape)
    reviews_cnt = models.IntegerField(null=True)
    reviews_scr = models.FloatField(null=True)
    rec_at = models.DateTimeField(db_index=True, null=True, blank=True)

    # reschedule prediction for cron pickup
    redo_requested_at = models.DateTimeField(null=True, blank=True)
    redo_started_at = models.DateTimeField(null=True, blank=True)
    redo_completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        name = f' ({self.name})' if self.name else ''
        return f'Player {self.nick}{name}'

    @property
    def bgg_link(self):
        return f'https://www.boardgamegeek.com/user/{self.nick}'

    def get_absolute_url(self) -> str:
        return f'/players/{self.id}'

    def geo(self):
        geo = ''
        if self.country:
            geo = self.country
        if self.area:
            geo += f' {self.area}'
        return geo or ''

    def is_rsa(self) -> bool:
        return self.country and self.country == 'South Africa'


class PlayerProxy(Player):
    class Meta:
        proxy = True


class Day(models.Model):
    day = models.DateField(db_index=True)

    reviews_cnt = models.IntegerField()
    reviews_avg = models.FloatField()
    last_review_id = models.IntegerField()
    last_review_update = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'<Day {self.day:"%y-%m-%d} cnt={self.reviews_cnt} avg={self.reviews_avg}>'

    @staticmethod
    def get_today() -> 'Day':
        today = now()
        day, _ = Day.objects.get_or_create(
            day=datetime(today.year, today.month, today.day),
            defaults={
                'reviews_cnt': 0,
                'reviews_avg': 0,
                'last_review_id': 0,
                'last_review_update': now(),
            }
        )
        return day


class GameDay(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='gamedays')
    day = models.ForeignKey(Day, on_delete=models.CASCADE, related_name='gamedays')

    reviews_cnt = models.IntegerField(db_index=True)
    reviews_avg = models.FloatField(db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('game', 'day')

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
    def diff_combine(self) -> float:
        return self.rating + self.diff

    @property
    def day(self) -> datetime:
        return self.reviewed_at.replace(hour=0, minute=0, second=0, microsecond=0)


class Award(models.Model):
    CHOICES_AWARDS = (
        (AWARD_GAME_OF_THE_MONTH, AWARD_GAME_OF_THE_MONTH),
        (AWARD_GAME_OF_THE_YEAR, AWARD_GAME_OF_THE_YEAR),
    )
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='awards', null=True)

    type = models.CharField(max_length=256, choices=CHOICES_AWARDS)
    description = models.CharField(max_length=256, null=True)
    badge = models.CharField(max_length=256, null=True)
    awarded_at = models.DateTimeField(null=True)
    score = models.FloatField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'<Award {self.description} game={self.game} score={int(self.score)}>'


class Rec(models.Model):
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name='recs')
    weight_tag = models.CharField(max_length=20, choices=CHOICES_WEIGHTS)
    best_players = models.PositiveSmallIntegerField()

    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name='recs', null=True)
    predicted = models.FloatField(null=True)
    is_primary = models.BooleanField(default=False)

    rec_at = models.DateTimeField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('player', 'weight_tag', 'best_players')

    def __str__(self) -> str:
        return f'<Rec {self.weight_tag} {self.best_players} {self.game.name} -> {self.player.nick}>'


class Shop(models.Model):
    SHOP_CHOICES = (
        (SHOP_RARU, SHOP_RARU),
        (SHOP_TAKEALOT, SHOP_TAKEALOT),
    )
    name = models.CharField(max_length=50, unique=True, choices=SHOP_CHOICES)
    host = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'{self.name}'


class ShopGame(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='shopgames')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='shopgames')
    url = models.CharField(max_length=250, unique=True, null=True, blank=True)
    url_at = models.DateTimeField()
    mia = models.BooleanField(default=False, blank=True)

    current_available = models.BooleanField(null=True, blank=True)
    current_price = models.FloatField(null=True, blank=True)
    mean_price = models.FloatField(null=True, blank=True)
    min_price = models.FloatField(null=True, blank=True)
    max_price = models.FloatField(null=True, blank=True)
    mean_saving = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('shop', 'game')

    def __str__(self) -> str:
        return f'{self.shop} {self.game} {self.mia}'


class Price(models.Model):
    STOCK_CHOICES = (
        (STOCK_IN, STOCK_IN),
        (STOCK_OUT, STOCK_OUT),
    )
    shopgame = models.ForeignKey(ShopGame, on_delete=models.CASCADE, related_name='prices')
    day = models.ForeignKey(Day, on_delete=models.CASCADE, related_name='prices')

    status = models.CharField(max_length=50, choices=STOCK_CHOICES)
    price = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('shopgame', 'day')

    def __str__(self) -> str:
        return f'Price {self.day}  {self.shopgame} {self.status} {self.price}'
