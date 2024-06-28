import contextlib
import logging

from django.core.management import BaseCommand
from django.db import OperationalError
from retry import retry

from main.scraper import (
    delete_most_insignificant_games,
    scrape_new_games,
    update_game_details_and_reviews,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape bgg for data'

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def _main(self, *args, **options):
        logger.info(''.join(['='] * 99))
        scrape_new_games()

        logger.info(''.join(['='] * 99))
        update_game_details_and_reviews()

        logger.info(''.join(['='] * 99))
        delete_most_insignificant_games()

        logger.info(''.join(['='] * 50) + ' scraping done ' + ''.join(['='] * 50))

    def handle(self, *args, **options):
        """Run the scraping games command."""
        with contextlib.suppress(Exception):
            self._main(*args, **options)
