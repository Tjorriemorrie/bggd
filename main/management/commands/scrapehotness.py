import contextlib
import logging

from django.core.management import BaseCommand

from main.scraper import scrape_hotness

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape boardgamegeek hotness'

    def handle(self, *args, **options):
        """Run the scraping games command."""
        with contextlib.suppress(Exception):
            logger.info(''.join(['='] * 99))
            scrape_hotness()
