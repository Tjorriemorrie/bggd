import logging

from django.core.management import BaseCommand
from django.db import OperationalError
from retry import retry

from main.constants import (
    SHOP_AMAZON,
    SHOP_BGBSA,
    SHOP_GARGOYLE,
    SHOP_GEEKHOME,
    SHOP_LEVEL_UP,
    SHOP_MEEPS_AND_VEEPS,
    SHOP_SWORD_AND_BOARD,
    SHOP_THD,
    SHOP_TIMELESS,
    SHOP_TTG,
)
from main.models import Game, Shop
from main.shops import scrape_site, update_outdated_game_shop_prices, validate_shopgames

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape shops'

    def add_arguments(self, parser):
        """Add shop name."""
        parser.add_argument('shop_name', nargs='+', type=str)
        parser.add_argument('--fail_fast', action='store_true')

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def _main(self, *args, **options):  # noqa PLR0912
        shop_names = options['shop_name']
        logger.info(f'cmd scraping shops {shop_names}')
        for shop_name in shop_names:
            if shop_name.lower() == 'mav':
                shop = Shop.objects.get(name=SHOP_MEEPS_AND_VEEPS)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'timeless':
                shop = Shop.objects.get(name=SHOP_TIMELESS)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'geekhome':
                shop = Shop.objects.get(name=SHOP_GEEKHOME)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'thd':
                shop = Shop.objects.get(name=SHOP_THD)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'ttg':
                shop = Shop.objects.get(name=SHOP_TTG)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'gargoyle':
                shop = Shop.objects.get(name=SHOP_GARGOYLE)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'swordandboard':
                shop = Shop.objects.get(name=SHOP_SWORD_AND_BOARD)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'levelup':
                shop = Shop.objects.get(name=SHOP_LEVEL_UP)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'amazon':
                shop = Shop.objects.get(name=SHOP_AMAZON)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'bgbsa':
                shop = Shop.objects.get(name=SHOP_BGBSA)
                scrape_site(shop, fail_fast=options.get('fail_fast'))

            elif shop_name.lower() == 'validate':
                validate_shopgames()

            elif shop_name.lower() == 'outdated':
                outs = (
                    Game.objects.filter(shop_available=True, shop_saving__gte=0)
                    .order_by('-shop_saving', '-hotness')
                    .all()[:20]
                )
                for out in outs:
                    out.shop_outdated = True
                    out.save()
                update_outdated_game_shop_prices()

            else:
                raise ValueError(f'Unknown shop name {shop_name}')
        logger.info('cmd done')

    def handle(self, *args, **options):
        """Scrape shops."""
        try:
            self._main(*args, **options)
        except Exception:
            logger.exception('Error during scraping shops!')
            raise
