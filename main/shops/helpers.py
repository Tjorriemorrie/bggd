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

from main.errors import ListingImageError, ListingIntegrityError, ListingUrlError
from main.games import get
from main.models import Listing, Price, Shop
from main.selectors import get_today

logger = logging.getLogger(__name__)


def base_scrape(worker):
    """Start scraping using multiprocessing with ProcessPoolExecutor."""
    process_pool_size = settings.PROCESS_POOL
    max_retries = 5  # Increased retries to 5 attempts
    retry_delay = 10  # Added 10s delay between retries

    pages_to_scrape = list(range(1, 5))
    failed_pages = {}  # Store pages that need retrying
    processed_pages = set()  # Track successfully processed pages
    executor_usable = True  # Flag to track executor usability
    executor = None  # Initialize executor variable
    future_to_page = {}  # Initialize future_to_page dictionary

    while pages_to_scrape or failed_pages or future_to_page:
        # Ensure a usable executor
        if not executor_usable or executor is None:
            # Shutdown previous executor (if it exists and not already shut down)
            if executor is not None:
                try:
                    executor.shutdown(wait=True)
                except RuntimeError as e:
                    if 'cannot shutdown already-shutdown' not in str(e).lower():
                        raise
            # Create a new executor
            executor = concurrent.futures.ProcessPoolExecutor(max_workers=process_pool_size)
            executor_usable = True
            future_to_page = {}  # Reset future_to_page for the new executor

        # Submit initial tasks or retry failed tasks
        if not future_to_page and (pages_to_scrape or failed_pages):
            for page in list(pages_to_scrape):
                future_to_page[executor.submit(worker, page)] = page
                pages_to_scrape.remove(page)
            for page, _ in list(failed_pages.items()):
                future_to_page[executor.submit(worker, page)] = page
                del failed_pages[page]

        # Handle completed futures
        for future in list(future_to_page):
            page = future_to_page[future]
            try:
                new_pages = future.result(timeout=300)
                # Add new pages to pages_to_scrape (if not already processed)
                for new_page in new_pages:
                    if new_page not in processed_pages and new_page not in pages_to_scrape:
                        pages_to_scrape.append(new_page)
                # Mark the current page as processed
                processed_pages.add(page)

            except concurrent.futures.process.BrokenProcessPool:
                logger.warning(f'BrokenProcessPool on page {page}. Retrying...')
                if page not in failed_pages:
                    failed_pages[page] = 0
                failed_pages[page] += 1
                if failed_pages[page] <= max_retries:
                    # Add a 10s delay before retrying
                    import time

                    time.sleep(retry_delay)
                    # Mark executor as unusable for the next iteration
                    executor_usable = False
                else:
                    logger.error(
                        f'Max retries ({max_retries}) exceeded for page {page}. Giving up.'
                    )
                    del failed_pages[page]
                    processed_pages.add(page)  # Ensure page is marked as processed

            except Exception as exc:
                logger.exception(f'Error with future on page {page}: {exc}')
                processed_pages.add(page)  # Ensure page is marked as processed on error
                raise

            # Remove completed future
            del future_to_page[future]

    # Final shutdown
    if executor is not None:
        try:
            executor.shutdown(wait=True)
        except RuntimeError as e:
            if 'cannot shutdown already-shutdown' not in str(e).lower():
                raise
        finally:
            executor = None


def strip_query_params(url: str) -> str:
    """Strip query params."""
    if not url.startswith('http'):
        raise ListingUrlError(f'http missing: {url}')
    # Parse the URL into components
    parsed_url = urlparse(url)
    # Rebuild the URL without query parameters (empty query part)
    stripped_url = urlunparse(parsed_url._replace(query=''))
    return stripped_url


def verify_image_url(url: str) -> bool:
    """Verify the image url."""
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
    """Update/create and store the listing in the db."""
    href = strip_query_params(href)
    img_src = strip_query_params(img_src)
    listing, created = Listing.objects.update_or_create(
        shop=shop,
        url=href,
        defaults={
            'name': name,
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
