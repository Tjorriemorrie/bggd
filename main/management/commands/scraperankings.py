import logging

from django.core.management import BaseCommand

from main.games import scrape_rankings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape rankings'

    def handle(self, *args, **options):
        """Scrape rankings."""
        logger.info(''.join(['='] * 99))
        try:
            scrape_rankings()
        except Exception as exc:
            logger.exception(exc)
