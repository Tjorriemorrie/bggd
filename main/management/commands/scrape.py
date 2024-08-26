import logging
import time

from django.core.management import BaseCommand

from main.models import CronSchedule
from main.scraper import scrape_hotness

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape boardgamegeek hotness'

    def add_arguments(self, parser):
        """Add arguments."""
        subparsers = parser.add_subparsers(
            title='sub-commands',
            required=True,
        )

        hotness_parser = subparsers.add_parser(
            'hotness',
            help='Scrape hotness.',
        )
        hotness_parser.set_defaults(method=self.scrape_hotness)

    def handle(self, *args, method, **options):
        """Run cmd."""
        method(*args, **options)

    def scrape_hotness(self, *args, **options):
        """Scrape hotness."""
        logger.info(''.join(['='] * 99))
        msg = 'OK'
        start_at = time.time()
        try:
            scrape_hotness()
        except Exception as exc:
            msg = str(exc)
        dur = time.time() - start_at
        CronSchedule.upart(
            {
                'hotness': msg,
                'hotness_dur': round(dur / 60, 1),
            }
        )
