import logging

from django.core.management import BaseCommand
from django.db import OperationalError
from retry import retry

from main.constants import SHOP_RARU, SHOP_TAKEALOT, SHOP_MEEPS_AND_VEEPS
from main.models import Game
from main.shops import scrape_raru, calc_shopgame_stats, scrape_takealot, \
    scrape_meeps_and_veeps, aggregate_shop, update_shopgame_stats

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape shops'

    def add_arguments(self, parser):
        parser.add_argument('shop_name', nargs='+', type=str)
        parser.add_argument('--fail_fast', action='store_true')

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def _main(self, *args, **options):
        shop_names = options['shop_name']
        logger.info(f'cmd scraping shops {shop_names}')
        for shop_name in shop_names:
            if shop_name.lower() == SHOP_RARU.lower():
                scrape_raru(fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == SHOP_TAKEALOT.lower():
                scrape_takealot(fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'mav':
                scrape_meeps_and_veeps(fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'frontpage':
                self._update_shop_page()
            elif shop_name.lower() == 'aggregate':
                self._update_game_aggregates()
            else:
                raise ValueError(f'Unknown shop name {shop_name}')
        logger.info('cmd done')

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def _update_shop_page(self, *args, **options):
        logger.info('Updating front shop page')
        top_20_games = Game.objects.filter(
            shop_available=True,
            shop_saving__gte=0
        ).order_by('-shop_saving', '-hotness').all()[:20]
        for game in top_20_games:
            best_shopgame = game.best_shop()
            logger.info(f'Updating shop for {best_shopgame}')
            update_shopgame_stats(best_shopgame)

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def _update_game_aggregates(self, *args, **options):
        """Update all the games aggregates about best shops."""
        games = Game.objects.all()
        for game in games:
            logger.info(f'Aggregating best shop for {game}')
            aggregate_shop(game)

    def handle(self, *args, **options):
        try:
            self._main(*args, **options)
        except Exception:
            logger.exception('Error during scraping shops!')
            raise
