import logging
import time

from django.core.management import BaseCommand
from django.db import OperationalError
from retry import retry

from main.models import CronSchedule
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
        msg = 'OK'
        start_at = time.time()
        try:
            self._main(*args, **options)
        except Exception as exc:
            msg = str(exc)
        dur = time.time() - start_at
        CronSchedule.upart(
            {
                'scrape_games': msg,
                'scrape_games_dur': round(dur / 60, 1),
            }
        )
