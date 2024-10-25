import logging
import time

from django.core.management import BaseCommand
from django.utils import timezone

from main.games import auto_assign_games, scrape_new_games, update_outdated_game_shop_prices
from main.models import Scrapelog
from main.selectors import get_today

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape BGG games.'

    def add_arguments(self, parser):
        """Add subparsers."""
        subparsers = parser.add_subparsers(dest='subcommand', required=True)

        # Subparser for 'auto'
        subparsers.add_parser('auto', help='Auto assign BGG games')

        # Subparser for 'new'
        subparsers.add_parser('new', help='Scrape new BGG games')

        # Subparser for 'out'
        subparsers.add_parser('out', help='Dummy scrape for out-of-stock games')

    def scrape_auto(self, *args, **options):
        """Auto assign games from search."""
        logger.info(''.center(99, '='))
        auto_assign_games()
        logger.info('Finished scraping new games'.center(50, '='))

    def scrape_new(self, *args, **options):
        """Scrape new games by their bgg_ids."""
        logger.info(''.center(99, '='))
        scrape_new_games()
        logger.info('Finished scraping new games'.center(50, '='))

    def scrape_out(self, *args, **options):
        """Update games with new shop information."""
        logger.info(''.center(99, '='))
        update_outdated_game_shop_prices()
        logger.info('Finished updating games with shop info'.center(50, '='))

    def handle(self, *args, **options):
        """Handle subcommands and call the appropriate method."""
        subcommand = options['subcommand']
        msg = 'OK'
        start_at = time.time()

        try:
            if subcommand == 'auto':
                self.scrape_auto(*args, **options)
                target = 'game auto'
            elif subcommand == 'new':
                self.scrape_new(*args, **options)
                target = 'game new'
            elif subcommand == 'out':
                self.scrape_out(*args, **options)
                target = 'game out'
            else:
                raise NotImplementedError(f'No such cmd found: {subcommand}')
        except Exception as exc:
            logger.exception(f'Problem with {subcommand}')
            msg = str(exc)

        dur = round(time.time() - start_at)
        today = get_today()

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
