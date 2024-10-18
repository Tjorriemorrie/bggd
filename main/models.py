import logging

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.timezone import now
from unidecode import unidecode

from main.constants import CHOICES_LABELS, CHOICES_WEIGHTS
from main.managers import ListingManager

logger = logging.getLogger(__name__)


class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Shop(Timestamped):
    name = models.CharField(max_length=50)
    slug = models.SlugField()

    def __str__(self) -> str:
        return unidecode(f'{self.name}')

    def get_absolute_url(self):
        """Get detail url."""
        return reverse('shop-detail-slug', kwargs={'pk': self.pk, 'slug': self.slug})

    @property
    def host(self):
        from main.shops import shop_hosts

        return shop_hosts[self.name]


class Label(Timestamped):
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=CHOICES_LABELS)

    def __str__(self):
        return unidecode(f'<Label-{self.id} [{self.type}] {self.name}>')


class Game(Timestamped):
    categories = models.ManyToManyField(Label, related_name='cat_games', blank=True)
    mechanics = models.ManyToManyField(Label, related_name='mec_games', blank=True)
    families = models.ManyToManyField(Label, related_name='fam_games', blank=True)
    subdomains = models.ManyToManyField(Label, related_name='dom_games', blank=True)

    name = models.CharField(max_length=250)
    slug = models.SlugField()
    label = models.CharField(max_length=50)
    year = models.IntegerField(
        validators=[MinValueValidator(-2500), MaxValueValidator(now().year + 1)]
    )
    url = models.CharField(max_length=250)
    rank = models.PositiveIntegerField(null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)

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
    weight_avg = models.FloatField(null=True, blank=True)
    weight_tag = models.CharField(max_length=20, choices=CHOICES_WEIGHTS, null=True, blank=True)

    # shops aggregate
    shop_best = models.ForeignKey(
        Shop, on_delete=models.SET_NULL, related_name='cheapest_games', null=True, blank=True
    )
    shop_in_stock = models.BooleanField(null=True, blank=True)
    shop_price = models.DecimalField(decimal_places=2, max_digits=9, null=True, blank=True)
    shop_mean = models.IntegerField(null=True, blank=True)
    shop_saving = models.FloatField(null=True, blank=True)
    shop_outdated = models.BooleanField(default=True)
    shop_updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return unidecode(f'{self.name} ({self.year})')

    def get_absolute_url(self):
        return reverse('game-detail-slug', kwargs={'pk': self.pk, 'slug': self.slug})


# class Player(Timestamped):
#     bgg_id = models.PositiveIntegerField(null=True)
#     nick = models.CharField(max_length=256, unique=True)
#
#     # updated in scrape
#     name = models.CharField(max_length=256, null=True, blank=True)
#     country = models.CharField(max_length=150, null=True, blank=True)
#     area = models.CharField(max_length=150, null=True, blank=True)
#     avatar = models.CharField(max_length=256, null=True, blank=True)
#     scraped_at = models.DateTimeField(db_index=True, null=True, blank=True)
#
#     # updated in predict (joined with scrape)
#     reviews_cnt = models.IntegerField(null=True)
#     reviews_scr = models.FloatField(null=True)
#     last_review_at = models.DateTimeField(db_index=True, null=True, blank=True)
#     rec_at = models.DateTimeField(db_index=True, null=True, blank=True)
#     is_outdated = models.BooleanField(db_index=True, default=False)
#
#     # reschedule prediction for cron pickup
#     redo_requested_at = models.DateTimeField(null=True, blank=True)
#     redo_started_at = models.DateTimeField(null=True, blank=True)
#     redo_completed_at = models.DateTimeField(null=True, blank=True)
#
#     def __str__(self) -> str:
#         name = f' ({self.name})' if self.name else ''
#         return f'Player {self.nick}{name}'
#
#     @property
#     def bgg_link(self):
#         """Get boardgamegeek url."""
#         return f'https://www.boardgamegeek.com/user/{self.nick}'
#
#     def get_absolute_url(self) -> str:
#         """Get absolute url for links."""
#         return f'/players/{self.id}'
#
#     def geo(self):
#         """Get geo location."""
#         geo = ''
#         if self.country:
#             geo = self.country
#         if self.area:
#             geo += f' {self.area}'
#         return geo or ''
#
#     def is_rsa(self) -> bool:
#         """Is south africa country."""
#         return self.country and self.country == 'South Africa'
#
#
# class PlayerProxy(Player):
#     class Meta:
#         proxy = True


class Day(Timestamped):
    day = models.DateField(primary_key=True)

    # reviews_cnt = models.IntegerField()
    # reviews_avg = models.FloatField()
    # last_review_id = models.IntegerField()
    # last_review_at = models.DateTimeField()
    # is_outdated = models.BooleanField(db_index=True, default=False)

    def __str__(self) -> str:
        return unidecode(f'{self.day:%y-%m-%d}')


# class Review(Timestamped):
#     player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='reviews')
#     game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='reviews')
#     gameday = models.ForeignKey(
#         GameDay, null=True, on_delete=models.SET_NULL, related_name='reviews'
#     )
#
#     bgg_id = models.PositiveIntegerField(db_index=True)
#     rating = models.FloatField(db_index=True)
#     comment = models.CharField(max_length=256, null=True)
#     reviewed_at = models.DateTimeField(db_index=True)
#     status = models.CharField(max_length=50, choices=REVIEW_STATUS_CHOICES)
#
#     # plays
#     num_plays = models.IntegerField(default=0)
#     last_played_at = models.DateTimeField(null=True)
#
#     predicted = models.FloatField(null=True)
#
#     class Meta:
#         unique_together = ('player', 'game')
#
#     def __str__(self) -> str:
#         return f'<Review-{self.bgg_id} {self.rating} {self.game.name} by {self.player.nick}>'
#
#     @property
#     def diff(self) -> float:
#         """Get the difference between predicted and rating."""
#         if not self.predicted:
#             return 0
#         return self.predicted - self.rating
#
#     @property
#     def diff_combine(self) -> float:
#         """Get rating and diff combined."""
#         return self.rating + self.diff
#
#     @property
#     def day(self) -> datetime:
#         """Get day of review."""
#         return self.reviewed_at.replace(hour=0, minute=0, second=0, microsecond=0)
#
#
# class Award(Timestamped):
#     CHOICES_AWARDS = (
#         (AWARD_GAME_OF_THE_MONTH, AWARD_GAME_OF_THE_MONTH),
#         (AWARD_GAME_OF_THE_YEAR, AWARD_GAME_OF_THE_YEAR),
#     )
#     game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='awards', null=True)
#
#     type = models.CharField(max_length=256, choices=CHOICES_AWARDS)
#     description = models.CharField(max_length=256, null=True)
#     badge = models.CharField(max_length=256, null=True)
#     awarded_at = models.DateTimeField(null=True)
#     score = models.FloatField(null=True)
#     num_ratings = models.IntegerField(null=True)
#
#     # runner up
#     ru_game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='runnerups', null=True)
#     ru_score = models.FloatField(null=True)
#     ru_num_ratings = models.IntegerField(null=True)
#
#     def __str__(self) -> str:
#         return f'<Award {self.description} game={self.game} score={int(self.score)}>'
#
#
# class Rec(Timestamped):
#     player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='recs')
#     weight_tag = models.CharField(max_length=20, choices=CHOICES_WEIGHTS)
#     best_players = models.PositiveSmallIntegerField()
#
#     game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='recs', null=True)
#     predicted = models.FloatField(null=True)
#     is_primary = models.BooleanField(default=False)
#
#     rec_at = models.DateTimeField(null=True)
#
#     def __str__(self) -> str:
#         return f'<Rec {self.weight_tag} {self.best_players} {self.game.name} -> {self.player.nick}>'


class Listing(Timestamped):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='listings')
    name = models.CharField(max_length=250)
    slug = models.SlugField()
    url = models.CharField(max_length=250, unique=True)
    img = models.CharField(max_length=250)
    scraped_at = models.DateField()

    # type
    is_accessory = models.BooleanField(default=False)
    is_new = models.BooleanField(default=True)
    is_preorder = models.BooleanField(default=False)

    # latest price
    in_stock = models.BooleanField(null=True)
    price = models.DecimalField(decimal_places=2, max_digits=9, null=True)
    priced_at = models.DateField(null=True)

    # boardgamegeek
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name='listings', null=True, blank=True
    )
    bgg_id = models.IntegerField(null=True, blank=True)
    bgg_missing = models.BooleanField(default=False)
    bgg_scraped = models.DateTimeField(null=True, blank=True)

    objects = ListingManager()

    def __str__(self):
        return unidecode(f'<Listing-{self.id} [{self.shop}] {self.name}>')

    def get_absolute_url(self):
        """Get detail url."""
        return reverse('listing-detail-slug', kwargs={'pk': self.pk, 'slug': self.slug})


class Price(Timestamped):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='prices')
    day = models.ForeignKey(Day, on_delete=models.PROTECT, related_name='prices')

    in_stock = models.BooleanField(default=True)
    price = models.DecimalField(decimal_places=2, max_digits=9, null=True)

    class Meta:
        unique_together = ('listing', 'day')

    def __str__(self) -> str:
        value = f'{self.price:.0f}' if self.in_stock else 'Out of Stock'
        return unidecode(f'<Price-{self.id} {self.day} {value} {self.listing}>')


# class Play(Timestamped):
#     player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='plays')
#     game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='plays')
#     day = models.ForeignKey(Day, on_delete=models.CASCADE, related_name='plays')
#     bgg_id = models.IntegerField()
#     duration = models.IntegerField(null=True)
#     num_players = models.IntegerField(null=True)
#
#     def __str__(self):
#         return f'<Play bggid={self.bgg_id} {self.game.name} by {self.player.nick} {self.day.day}>'


class Scrapelog(Timestamped):
    day = models.ForeignKey(Day, on_delete=models.PROTECT, related_name='scrapelogs')
    target = models.CharField(max_length=250)
    scraped_at = models.DateTimeField()
    outcome = models.CharField(max_length=255)
    duration = models.IntegerField()

    class Meta:
        unique_together = ['day', 'target']

    def __str__(self):
        return unidecode(f'<Scrapelog-{self.id} {self.day} {self.target}>')
