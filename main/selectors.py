import datetime
import logging
import multiprocessing

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.text import slugify
from unidecode import unidecode

from main.models import Day, Game, Listing, Scrapelog, Shop

logger = logging.getLogger(__name__)


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


def get_best_savings_games() -> QuerySet[Game]:
    """Get the best savings games."""
    games = Game.objects.order_by('-shop_saving', '-shop_price').all()[:18]
    return games


def list_listings_without_games() -> QuerySet[Listing]:
    """Gives listings without bgg_ids."""
    listings = Listing.objects.filter(bgg_id__isnull=True, bgg_missing=False).order_by('-price')
    return listings


def best_listing_by_game(game: Game) -> Listing | None:
    """Returns best listing with available stock."""
    return game.listings.filter(in_stock=True, price__isnull=False).order_by('price').first()


def get_last_scrape(shop: Shop) -> Scrapelog | None:
    """Last scrape of shop."""
    scrapelog = Scrapelog.objects.filter(target=f'shop {shop.name}').order_by('scraped_at').last()
    return scrapelog


def list_newwest_games():
    """List newest games."""
    games = Game.objects.order_by('-created_at').all()[:18]
    return games
