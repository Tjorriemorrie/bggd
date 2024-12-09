import datetime
import logging
import multiprocessing
from itertools import chain

from django.db import transaction
from django.db.models import ExpressionWrapper, F, FloatField, Func, QuerySet, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.text import slugify
from unidecode import unidecode

from main.models import Day, Game, Listing, Scrapelog, Shop

logger = logging.getLogger(__name__)


class UnixTimestamp(Func):
    function = 'strftime'
    template = "%(function)s('%%%%s', %(expressions)s)"  # Escape % with %%
    output_field = FloatField()  # Explicitly declare the output as FloatField


def get_today() -> Day:
    """Get today as model instance."""
    today = timezone.now()
    day, _ = Day.objects.get_or_create(
        day=datetime.datetime(today.year, today.month, today.day),
        defaults={
            # 'reviews_cnt': 0,
            # 'reviews_avg': 0,
            # 'last_review_id': 0,
            # 'last_review_at': now(),
        },
    )
    return day


def get_day_at(date_val) -> Day:
    """Get specific day from string."""
    day, day_created = Day.objects.get_or_create(
        day=date_val,
        defaults={
            # 'reviews_cnt': 0,
            # 'reviews_avg': 0,
            # 'last_review_id': 0,
            # 'last_review_at': now(),
        },
    )
    if day_created:
        logger.info(f'Created day! {day}')
    return day


# Create a process-safe lock
shop_lock = multiprocessing.Lock()


def upsert_shop(shop_name: str) -> Shop:
    """Get shop by name."""
    with shop_lock, transaction.atomic():
        shop, created = Shop.objects.get_or_create(
            name=shop_name,
            defaults={
                'slug': slugify(unidecode(shop_name)),
            },
        )
        if created:
            logger.info(f'Created shop {shop}')
        return shop


def get_latest_new_games() -> QuerySet[Game]:
    """Get latest new games."""
    games = Game.objects.order_by('-created_at').all()[:12]
    return games


def get_best_savings_games(reverse: bool = False) -> QuerySet[Game]:
    """Get the best savings games."""
    games = Game.objects.order_by(f'{"" if reverse else "-"}shop_saving', '-shop_price').all()[:18]
    return games


def list_listings_without_games() -> QuerySet[Listing]:
    """Gives listings without bgg_ids."""
    # first get any unlooked that is missing
    listings = Listing.objects.filter(bgg_looked_at__isnull=True, bgg_missing=True).order_by(
        '-price'
    )
    if listings:
        return listings

    # make sure home page is all correct
    savings = get_best_savings_games()
    worst = get_best_savings_games(reverse=True)
    latest = list_newest_games()
    home_page_game_ids = [g.id for g in chain(savings, latest, worst)]
    listings = Listing.objects.filter(
        bgg_looked_at__isnull=True, game_id__in=home_page_game_ids
    ).order_by('-price')
    if listings:
        return listings

    # else sort it by discount
    listings = Listing.objects.filter(
        bgg_looked_at__isnull=True, game__isnull=False, game__shop_saving__gt=0
    ).order_by('-game__shop_saving')
    if listings:
        return listings

    # recently created listings
    days_ago = timezone.now() - datetime.timedelta(days=7)
    listings = Listing.objects.filter(bgg_looked_at__isnull=True, created_at__gt=days_ago).order_by(
        '-price'
    )
    if listings:
        return listings

    # lastly just by updated date
    listings = Listing.objects.filter(bgg_looked_at__isnull=True).order_by('-in_stock', '-price')
    if listings:
        return listings

    # otherwise just rotate from oldest
    listings = (
        Listing.objects.annotate(
            bgg_looked_at_timestamp=Coalesce(
                UnixTimestamp(F('bgg_looked_at')), Value(0.0, output_field=FloatField())
            ),
            updated_at_timestamp=Coalesce(
                UnixTimestamp(F('updated_at')), Value(0.0, output_field=FloatField())
            ),
        )
        .annotate(
            diff_fields=ExpressionWrapper(
                F('updated_at_timestamp') - F('bgg_looked_at_timestamp'), output_field=FloatField()
            )
        )
        .order_by('-diff_fields')
    )
    return listings


def best_listing_by_game(game: Game) -> Listing | None:
    """Returns best listing with available stock."""
    return game.listings.filter(in_stock=True, price__isnull=False).order_by('price').first()


def get_last_scrape(shop: Shop) -> Scrapelog | None:
    """Last scrape of shop."""
    scrapelog = Scrapelog.objects.filter(target=f'shop {shop.name}').order_by('scraped_at').last()
    return scrapelog


def list_newest_games():
    """List newest games."""
    price_cutoff = 1_100
    max_num = 18
    days = 4
    while True:
        days_ago = timezone.now() - datetime.timedelta(days=days)
        games = (
            Game.objects.filter(
                created_at__gt=days_ago, shop_in_stock=True, shop_price__gt=price_cutoff
            )
            .order_by('-created_at')
            .all()[:max_num]
        )
        if len(games) >= max_num:
            return games
        days += 1
