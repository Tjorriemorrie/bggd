import logging

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.timezone import now
from unidecode import unidecode

from main.constants import CATEGORY_CHOICES, CHOICES_LABELS, CHOICES_WEIGHTS

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
        """Get host."""
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
    slug = models.SlugField(max_length=250)
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

    # fix me
    fix_me = models.BooleanField(default=False)

    def __str__(self) -> str:
        return unidecode(f'{self.name} ({self.year})')

    def get_absolute_url(self):
        """Get detail url."""
        return reverse('game-detail-slug', kwargs={'pk': self.pk, 'slug': self.slug})


class Day(Timestamped):
    day = models.DateField(primary_key=True)

    def __str__(self) -> str:
        return unidecode(f'{self.day:%y-%m-%d}')


class Listing(Timestamped):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='listings')
    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=250)
    url = models.CharField(max_length=250, unique=True)
    img = models.CharField(max_length=250)
    scraped_at = models.DateTimeField()

    # type
    is_accessory = models.BooleanField(default=False)
    is_new = models.BooleanField(default=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, null=True, blank=True)

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
    bgg_scraped_at = models.DateTimeField(null=True, blank=True)
    bgg_looked_at = models.DateTimeField(null=True, blank=True)

    # objects = ListingManager()

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


class PageView(Timestamped):
    day = models.ForeignKey(Day, on_delete=models.PROTECT, related_name='pageviews')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='pageviews')
    ip = models.GenericIPAddressField()
    viewed_at = models.DateTimeField()

    class Meta:
        unique_together = ['day', 'game', 'ip']

    def __str__(self):
        return unidecode(f'<PageView-{self.id} {self.ip} {self.day} {self.game}>')
