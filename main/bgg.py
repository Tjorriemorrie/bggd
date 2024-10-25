import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool

import django
from django.utils import timezone

from main.errors import BggGameNotFoundError

django.setup()
logger = logging.getLogger(__name__)


def scrape_new_games():
    """Newly added games need to get scraped."""
    from django.conf import settings

    from main.models import Listing

    logger.info('Scraping new games...')

    listings = Listing.objects.filter(bgg_id__isnull=False, bgg_missing=False, game__isnull=True)

    total = listings.count()
    logger.info(f'Found {total} listings to scrape.')

    if total == 0:
        logger.info('No new games to scrape.')
        return

    listing_ids = [listing.id for listing in listings]
    total = len(listing_ids)
    retries = 0
    max_retries = 10
    wait_seconds = 10
    while retries < max_retries:
        try:
            idx = 0
            # Initialize the process pool
            with ProcessPoolExecutor(max_workers=settings.PROCESS_POOL) as executor:
                future_to_id = {
                    executor.submit(scrape_game_worker, listing_id): listing_id
                    for listing_id in listing_ids
                }

                for future in as_completed(future_to_id):
                    listing_id = future_to_id[future]
                    try:
                        future.result()  # This will raise an exception if the worker failed
                        idx += 1
                        logger.info(
                            f'{idx}/{total} Successfully processed listing ID: {listing_id}'
                        )
                    except Exception as exc:
                        logger.exception(f'Error processing listing ID {listing_id}: {exc}')

            # If the pool completes successfully, break out of the retry loop
            break

        except BrokenProcessPool as bpp:
            # Log the BrokenProcessPool error
            logger.error(
                f'BrokenProcessPool error encountered. Attempt {retries + 1}/{max_retries}: {bpp}'
            )
            retries += 1
            if retries < max_retries:
                logger.info(f'Retrying in {wait_seconds} seconds...')
                time.sleep(wait_seconds)
            else:
                logger.error('Max retries reached. Exiting...')
                raise


def scrape_game_worker(listing_id):
    """Worker function to scrape a game based on its listing ID."""
    # Ensure Django is set up correctly within the worker
    from django.db import transaction

    from main.games import scrape_game
    from main.models import Listing

    try:
        # logger.info(f'Starting scrape for listing ID: {listing_id}')

        # Fetch the Listing instance within the worker
        listing = Listing.objects.get(id=listing_id)
        # logger.info(f'Fetched listing: {listing} with bgg_id: {listing.bgg_id}')

        with transaction.atomic():
            game = scrape_game(listing.bgg_id)
            game.shop_outdated = True
            game.save()

            listing.game = game
            listing.bgg_missing = False
            listing.bgg_scraped_at = timezone.now()
            listing.save()
        # logger.info(f'Successfully scraped and saved game for listing ID: {listing_id}')

    except Listing.DoesNotExist:
        logger.warning(f'Listing with id {listing_id} does not exist.')
    except BggGameNotFoundError:
        logger.warning(f'Boardgamegeek id {listing.bgg_id} not found!')
        listing.bgg_id = None
        listing.bgg_missing = True
        listing.bgg_scraped_at = timezone.now()
        listing.save()
    except Exception as exc:
        logger.exception(f'Unexpected error while scraping listing ID {listing_id}: {exc}')
