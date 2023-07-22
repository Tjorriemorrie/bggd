from datetime import datetime
from typing import List, Optional

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.timezone import now

from main.constants import WEIGHT_HEAVY, WEIGHT_MEDIUM, WEIGHT_LIGHT, STOCK_IN, \
    STOCK_OUT, SHOP_MEEPS_AND_VEEPS, SHOP_TIMELESS, \
    LABEL_CATEGORY, LABEL_MECHANIC, LABEL_FAMILY, LABEL_SUBDOMAIN, \
    AWARD_GAME_OF_THE_YEAR, AWARD_GAME_OF_THE_MONTH, IGNORE_FAMILIES, \
    SHOP_GEEKHOME, SHOP_THD, SHOP_TTG, SHOP_GARGOYLE, REVIEW_STATUS_CHOICES

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
    similars = models.ManyToManyField('Game', symmetrical=False, related_name='rev_similars')
    sim_at = models.DateTimeField(null=True, blank=True)

    # shops aggregate
    shop_available = models.BooleanField(null=True, blank=True)
    shop_price = models.IntegerField(null=True, blank=True)
    shop_mean = models.IntegerField(null=True, blank=True)
    shop_saving = models.FloatField(null=True, blank=True)
    shop_outdated = models.BooleanField(default=False)
    shop_updated_at = models.DateTimeField(null=True, blank=True)

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
        """Returns best shop with available stock."""
        return self.shopgames.filter(
            current_available=True,
            url__isnull=False
        ).order_by('current_price').first()

    def comments(self) -> List['Review']:
        return self.reviews.filter(
            comment__isnull=False,
            player__reviews_scr__isnull=False
        ).order_by('-player__reviews_scr')

    def similar(self) -> List['Game']:
        """Returns similar games from kmean clustering."""
        if not self.sim_cluster:
            return []
        return Game.objects.exclude(id=self.id).filter(
            sim_cluster=self.sim_cluster).all()

    def mechanics_comma(self) -> str:
        return ', '.join([m.name for m in self.mechanics.all()])

    def good_families(self) -> List[Label]:
        return [
            f for f in self.families.all() if not
            any(ig in f.name for ig in IGNORE_FAMILIES)]

    def families_comma(self) -> str:
        return ', '.join([f.name for f in self.families.all()])

    def categories_comma(self) -> str:
        return ', '.join([c.name for c in self.categories.all()])

    def players_fmt(self) -> str:
        """Show players on game detail page"""
        cnts = []
        for cnt in range(1, 9):
            if self.best_min_players <= cnt <= self.best_max_players:
                cnts.append(f'<strong style="font-size: 1.1em">{cnt}</strong>')
            elif self.rec_min_players <= cnt <= self.rec_max_players:
                cnts.append(f'{cnt}')
            elif self.min_players <= cnt <= self.max_players:
                cnts.append(f'<small class="text-muted">{cnt}</small>')
        return mark_safe('&nbsp;'.join(cnts))

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
    last_review_at = models.DateTimeField(db_index=True, null=True, blank=True)
    rec_at = models.DateTimeField(db_index=True, null=True, blank=True)
    is_outdated = models.BooleanField(db_index=True, default=False)

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
    last_review_at = models.DateTimeField()
    is_outdated = models.BooleanField(db_index=True, default=False)

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
                'last_review_at': now(),
            }
        )
        return day


class GameDay(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='gamedays')
    day = models.ForeignKey(Day, on_delete=models.CASCADE, related_name='gamedays')

    # reviews per day aggregation
    reviews_cnt = models.IntegerField(db_index=True)
    reviews_avg = models.FloatField(db_index=True)
    is_outdated = models.BooleanField(db_index=True, default=False)

    # best and mean price aggregation
    shop_best = models.FloatField(null=True, blank=True)
    shop_mean = models.FloatField(null=True, blank=True)
    shop_saving = models.FloatField(null=True, blank=True)

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
    status = models.CharField(max_length=50, choices=REVIEW_STATUS_CHOICES)

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
        return self.predicted - self.rating

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
    num_ratings = models.IntegerField(null=True)

    # runner up
    ru_game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='runnerups', null=True)
    ru_score = models.FloatField(null=True)
    ru_num_ratings = models.IntegerField(null=True)

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

    def __str__(self) -> str:
        return f'<Rec {self.weight_tag} {self.best_players} {self.game.name} -> {self.player.nick}>'


class Shop(models.Model):
    SHOP_CHOICES = (
        (SHOP_MEEPS_AND_VEEPS, SHOP_MEEPS_AND_VEEPS),
        (SHOP_TIMELESS, SHOP_TIMELESS),
        (SHOP_GEEKHOME, SHOP_GEEKHOME),
        (SHOP_THD, SHOP_THD),
        (SHOP_TTG, SHOP_TTG),
        (SHOP_GARGOYLE, SHOP_GARGOYLE),
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
    current_price = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('shop', 'game')

    def __str__(self) -> str:
        tail = 'mia' if self.mia else 'n/a' if not self.current_available else f'R{self.current_price}'
        return f'<{self.shop} + {self.game} = {tail}>'

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if self.current_available is True and self.current_price == 0:
            raise ValueError(f'Cannot be free: {self}')
        super().save(force_insert, force_update, using, update_fields)


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
