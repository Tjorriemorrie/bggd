import logging
import time

from django.core.management import BaseCommand
from django.db import OperationalError
from django.utils import timezone
from retry import retry

from main.bgg import scrape_new_games
from main.games import update_outdated_game_shop_prices
from main.models import Scrapelog
from main.selectors import get_today

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape BGG games.'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='subcommand', required=True)

        # Subparser for 'new'
        new_parser = subparsers.add_parser('new', help='Scrape new BGG games')

        # Subparser for 'out'
        out_parser = subparsers.add_parser('out', help='Dummy scrape for out-of-stock games')

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def scrape_new(self, *args, **options):
        """Scrape new games by their bgg_ids."""
        logger.info('Scraping new games'.center(50, '='))
        scrape_new_games()
        logger.info('Finished scraping new games'.center(50, '='))

    def scrape_out(self, *args, **options):
        """Update games with new shop information."""
        logger.info('Update games with shop info'.center(50, '='))
        update_outdated_game_shop_prices()
        logger.info('Finished updating games with shop info'.center(50, '='))

    def handle(self, *args, **options):
        """Handle subcommands and call the appropriate method."""
        subcommand = options['subcommand']
        msg = 'OK'
        start_at = time.time()

        try:
            if subcommand == 'new':
                self.scrape_new(*args, **options)
            elif subcommand == 'out':
                self.scrape_out(*args, **options)
            else:
                raise NotImplementedError(f'No such cmd found: {subcommand}')
        except Exception as exc:
            logger.exception(f'Problem with {subcommand}')
            msg = str(exc)

        dur = round(time.time() - start_at)
        today = get_today()

        if subcommand == 'new':
            target = 'game new'
        else:
            target = 'game out'

        scrapelog, created = Scrapelog.objects.update_or_create(
            day=today,
            target=target,
            defaults={
                'scraped_at': timezone.now(),
                'outcome': msg,
                'duration': dur,
            },
        )

        logger.info(f'{"Created" if created else "Updated"} {scrapelog}')
