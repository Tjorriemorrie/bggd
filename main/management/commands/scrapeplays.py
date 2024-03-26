import logging

from django.core.management import BaseCommand

from main.models import Player
from main.plays import scrape_plays

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape player plays'

    def add_arguments(self, parser):
        """Add username for script."""
        parser.add_argument('username', type=str)

    def handle(self, *args, **options):
        """Scrape player plays."""
        logger.info(f'Scraping player plays for {options}')
        player = Player.objects.get(nick__iexact=options['username'])
        scrape_plays(player)
        logger.info('Done scraping plays')
