import concurrent
import logging
import re
from datetime import timedelta
from urllib.parse import urlparse, urlunparse

import requests
from django.conf import settings
from django.db import OperationalError
from django.utils import timezone
from django.utils.text import slugify
from retry import retry
from unidecode import unidecode

from main.errors import ListingImageError, ListingIntegrityError
from main.games import get
from main.models import Listing, Price, Shop
from main.selectors import get_today

logger = logging.getLogger(__name__)


def base_scrape(worker):
    """Start scraping using multiprocessing with ProcessPoolExecutor."""
    # fork_context = mp.get_context('fork')
    # spawn_context = multiprocessing.get_context('spawn')  # Use 'spawn' on Windows

    process_pool_size = settings.PROCESS_POOL
    with concurrent.futures.ProcessPoolExecutor(max_workers=process_pool_size) as executor:
        pages_to_scrape = list(range(1, 5))
        future_to_page = {executor.submit(worker, page): page for page in pages_to_scrape}

        try:
            while future_to_page:
                # As workers finish, collect results and submit new tasks
                for future in concurrent.futures.as_completed(future_to_page):
                    page = future_to_page.pop(future)

                    try:
                        new_pages = future.result(timeout=30)
                        for new_page in new_pages:
                            if new_page not in pages_to_scrape:
                                pages_to_scrape.append(new_page)
                                future_to_page[executor.submit(worker, new_page)] = new_page

                    except Exception as exc:
                        logger.exception(f'Error with future on page {page}: {exc}')
        finally:
            executor.shutdown(wait=True)


def strip_query_params(url: str) -> str:
    # Parse the URL into components
    parsed_url = urlparse(url)
    # Rebuild the URL without query parameters (empty query part)
    stripped_url = urlunparse(parsed_url._replace(query=''))
    return stripped_url


def verify_image_url(url: str) -> bool:
    try:
        response = get(url)
    except requests.RequestException as exc:
        logger.info(f'{exc}')
        return False

    # Verify the content type is an image
    if 'image' not in response.headers['Content-Type']:
        logger.info(f'URL is accessible but is not an image: {url}')
        return False

    return True


def parse_price(price_txt) -> float:
    """Parse price."""
    match = re.search(r'R\s?([\d,]+(\.\d{2})?)', price_txt)
    if not match:
        raise ValueError(f'Could not extract price: {price_txt}')
    price = float(match.group(1).replace(',', ''))
    return price


@retry((OperationalError,), tries=99, delay=1, backoff=1, jitter=1, max_delay=30, logger=logger)
def upsert_listing(shop: Shop, name: str, href: str, img_src: str, **params) -> Listing:
    """update/create and store the listing in the db"""
    href = strip_query_params(href)
    img_src = strip_query_params(img_src)
    listing, created = Listing.objects.update_or_create(
        shop=shop,
        name=name,
        url=href,
        defaults={
            'slug': slugify(unidecode(name)),
            'img': img_src,
            'scraped_at': timezone.now(),
            **params,
        },
    )
    if created:
        logger.info(f'Listing created: {listing}')
    return listing


def handle_item_data(shop, name, href, img_src, in_stock, price_value, **params):
    """Handle exceptions on upserts."""
    try:
        listing = upsert_listing(shop, name, href, img_src, **params)
    except (ListingImageError, ListingIntegrityError):
        return
    price = upsert_price(listing, in_stock, price_value)
    logger.info(f'{listing} has price {price}')


@retry((OperationalError,), tries=99, delay=1, backoff=1, jitter=1, max_delay=30, logger=logger)
def upsert_price(listing: Listing, in_stock: bool, value: float) -> Price:
    """Upsert new price if different."""
    day = get_today()
    prev_price = listing.prices.last()
    if not prev_price or prev_price.price != value or prev_price.in_stock != in_stock:
        # create the new price
        new_price, created = Price.objects.update_or_create(
            listing=listing,
            day=day,
            defaults={
                'in_stock': in_stock,
                'price': value,
            },
        )
        logger.info(f'{"New" if created else "Updated"} Price: {new_price}')

        update_listing_with_price(listing, new_price)

        return new_price
    return prev_price


@retry((OperationalError,), tries=99, delay=1, backoff=1, jitter=1, max_delay=30, logger=logger)
def update_listing_with_price(listing: Listing, price: Price):
    """Update the listing with latest price info."""
    if price.in_stock:
        listing.in_stock = True
        listing.price = price.price
    else:
        listing.in_stock = False
        listing.price = None
    listing.priced_at = price.day.day
    listing.save()

    # outdate game if applicable
    if listing.game:
        listing.game.shop_outdated = True
        listing.game.save()


def missed_listings(shop: Shop):
    """Set missing listings as out of stock."""
    hours_30 = timezone.now() - timedelta(hours=30)
    missings = Listing.objects.prefetch_related('game').filter(
        shop=shop, scraped_at__lt=hours_30, in_stock=True
    )
    today = get_today()
    for missing in missings:
        Price.objects.create(
            listing=missing,
            day=today,
            in_stock=False,
        )
        missing.in_stock = False
        missing.price = None
        missing.scraped_at = timezone.now()
        missing.save()

        if missing.game:
            missing.game.shop_outdated = True
            missing.game.save()

        logger.info(f'Missing {missing}')
