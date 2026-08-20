import concurrent
import logging
import re
from datetime import timedelta
from urllib.parse import urlparse, urlunparse

import requests
from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from django.utils.text import slugify
from retry import retry
from unidecode import unidecode

from main.errors import ListingImageError, ListingUrlError
from main.games import get
from main.models import Listing, Price, Shop
from main.selectors import get_today
from main.sleeves import parse_sleeve_size

logger = logging.getLogger(__name__)


def base_scrape(worker):  # noqa: PLR0912, PLR0915
    """Start scraping using multiprocessing with ProcessPoolExecutor."""
    process_pool_size = settings.PROCESS_POOL
    max_retries = 50
    retry_delay = 10

    broken_pools = 0
    pages_to_scrape = list(range(1, 5))
    processed_pages = set()  # Track successfully processed pages
    executor_usable = True  # Flag to track executor usability
    executor = None  # Initialize executor variable
    future_to_page = {}  # Initialize future_to_page dictionary

    while pages_to_scrape:
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
        if not future_to_page and pages_to_scrape:
            for page in list(pages_to_scrape):
                future_to_page[executor.submit(worker, page)] = page
                pages_to_scrape.remove(page)

        # Handle completed futures
        for future in list(future_to_page):
            page = future_to_page[future]
            try:
                new_pages = future.result(timeout=30)
                # Add new pages to pages_to_scrape (if not already processed)
                for new_page in new_pages:
                    if (
                        new_page not in processed_pages
                        and new_page not in pages_to_scrape
                        and new_page not in future_to_page.values()
                    ):
                        pages_to_scrape.append(new_page)
                # Mark the current page as processed
                processed_pages.add(page)

            except concurrent.futures.process.BrokenProcessPool:
                logger.warning(f'BrokenProcessPool on page {page}. Retrying...')
                broken_pools += 1
                if broken_pools > max_retries:
                    logger.error(f'Not adding page {page} back for perm broken pool')
                    processed_pages.add(page)
                else:
                    # add page back to list to scrape
                    pages_to_scrape.append(page)
                    # Mark executor as unusable for the next iteration
                    executor_usable = False
                    import time

                    time.sleep(retry_delay)

            except Exception as exc:
                logger.exception(f'Error with future on page {page}: {exc}')
                processed_pages.add(page)
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
    if not url or not url.startswith('http'):
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
    price_txt = re.sub(r'\s+', '', price_txt)
    price_txt = price_txt.replace(',', '')
    match = re.search(r'R\s*([\d.,]+)', price_txt)
    if not match:
        raise ValueError(f'Could not extract price: {price_txt}')
    # Remove all whitespace characters including non-breaking space
    raw_amount = match.group(1)
    cleaned_amount = raw_amount.replace('\xa0', '').replace(' ', '')
    if ',' in cleaned_amount and '.' not in cleaned_amount:
        cleaned_amount = cleaned_amount.replace(',', '.')
    cleaned_amount = cleaned_amount.replace(',', '')
    amount = float(cleaned_amount)
    return amount


@retry((OperationalError,), tries=99, delay=1, logger=logger)
def upsert_listing(
    shop: Shop, name: str, href: str, img_src: str, create_defaults=None, **params
) -> Listing:
    """Update/create and store the listing in the db.

    `create_defaults` are only applied when the listing is first created, so they
    do not overwrite values edited later (e.g. a manually changed category).
    """
    href = strip_query_params(href)
    img_src = strip_query_params(img_src)
    # A sleeve carries the card size it fits in the name the shop printed, so it
    # is read here rather than at each shop: every listing gets a size or nulls.
    sleeve_width, sleeve_height = parse_sleeve_size(name) or (None, None)

    with transaction.atomic():
        try:
            listing = Listing.objects.get(shop=shop, url=href)
            for key, value in params.items():
                setattr(listing, key, value)
            listing.img = img_src
            listing.scraped_at = timezone.now()
            listing.sleeve_width = sleeve_width
            listing.sleeve_height = sleeve_height
            listing.save()
            return listing
        except Listing.DoesNotExist:
            pass

        try:
            listing = Listing.objects.create(
                shop=shop,
                url=href,
                name=name,
                slug=slugify(unidecode(name)),
                img=img_src,
                scraped_at=timezone.now(),
                sleeve_width=sleeve_width,
                sleeve_height=sleeve_height,
                **{**(create_defaults or {}), **params},
            )
            logger.info(f'Created: {listing}')
            return listing
        except IntegrityError as exc:
            logger.error(
                f'Failed to upsert listing due to unique constraint violation, for "{href}"'
            )
            raise ListingUrlError(f'Integrity error for {href}') from exc
        # try:
        #     bad_listing = Listing.objects.get(url=href)
        #     with transaction.atomic():
        #         bad_listing.delete()
        # except Listing.DoesNotExist:
        #     try:
        #         with connection.cursor() as cursor:
        #             cursor.execute(
        #                 'DELETE FROM main_price '
        #                 'WHERE listing_id IN (SELECT id FROM main_listing WHERE url = ?)',
        #                 [href],
        #             )
        #         with connection.cursor() as cursor:
        #             cursor.execute('DELETE FROM main_listing WHERE url = ?', [href])
        #     except TypeError as exc:
        #         raise ListingUrlError(
        #             f'Could not fix bad listing at {shop} with url {href}'
        #         ) from exc
        # return upsert_listing(shop, name, href, img_src, **params)


def handle_item_data(
    shop, name, href, img_src, in_stock, price_value, create_defaults=None, **params
):
    """Handle exceptions on upserts."""
    try:
        listing = upsert_listing(
            shop, name, href, img_src, create_defaults=create_defaults, **params
        )
    except (ListingUrlError, ListingImageError):
        logger.error('Could not handle item data')
        return
    new_price, price_created = upsert_price(listing, in_stock, price_value)
    if price_created:
        update_listing_with_price(listing, new_price)

    # logger.info(f'{listing} has price {price}')


@retry((OperationalError,), tries=99, delay=1, logger=logger)
def upsert_price(listing: Listing, in_stock: bool, value: float) -> tuple[Price, bool]:
    """Upsert new price if different."""
    day = get_today()
    prev_price = listing.prices.last()
    with transaction.atomic():
        # create first price ever
        if not prev_price:
            new_price = Price.objects.create(
                listing=listing, day=day, in_stock=in_stock, price=value
            )
            logger.info(f'Created {new_price}')
            return new_price, True

        # create new price if value changed
        prev_value = float(prev_price.price) if prev_price.price is not None else None
        if prev_value != value or prev_price.in_stock != in_stock:
            # only update changes on same day
            if prev_price.day == day:
                prev_price.price = value
                prev_price.in_stock = in_stock
                prev_price.save()
                logger.info(f'Updated existing price on this day {prev_price}')
                return prev_price, True

            # create new
            else:
                new_price = Price.objects.create(
                    listing=listing, day=day, in_stock=in_stock, price=value
                )
                logger.info(f'Created {new_price}')
                return new_price, True

    return prev_price, False


@retry((OperationalError,), tries=99, delay=1, logger=logger)
def update_listing_with_price(listing: Listing, price: Price):
    """Update the listing with latest price info."""
    with transaction.atomic():
        if price.in_stock:
            listing.in_stock = True
            listing.price = price.price
        else:
            listing.in_stock = False
            listing.price = None
        listing.priced_at = price.day.day
        listing.scraped_at = timezone.now()  # although in upsert, also from missing
        listing.save()

        # outdate game if applicable
        if listing.game:
            listing.game.shop_outdated = True
            listing.game.save()


@retry((OperationalError,), tries=99, delay=1, logger=logger)
def missed_listings(shop: Shop):
    """Set missing listings as out of stock."""
    hours_ago = timezone.now() - timedelta(hours=1)
    missings = Listing.objects.prefetch_related('game').filter(
        shop=shop, scraped_at__lt=hours_ago, in_stock=True
    )
    logger.info(f'Marking {len(missings)} listings as out of stock (missing).')
    today = get_today()
    for missing in missings:
        new_price, _ = Price.objects.update_or_create(
            listing=missing, day=today, defaults={'in_stock': False}
        )

        update_listing_with_price(missing, new_price)
        logger.info(f'Missing {missing}')
