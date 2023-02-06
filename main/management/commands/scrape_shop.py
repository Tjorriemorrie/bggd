import logging

from django.core.management import BaseCommand
from django.db import OperationalError
from retry import retry

from main.constants import SHOP_RARU, SHOP_TAKEALOT, SHOP_THD, SHOP_TTG, SHOP_MEEPS_AND_VEEPS, SHOP_TIMELESS, \
    SHOP_GEEKHOME
from main.models import Shop, Game
from main.shops import validate_shopgames, update_outdated_game_shop_prices, \
    scrape_site

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
                shop = Shop.objects.get(name=SHOP_RARU)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == SHOP_TAKEALOT.lower():
                shop = Shop.objects.get(name=SHOP_TAKEALOT)
                scrape_site(shop, fail_fast=options.get('fail_fast'))
            elif shop_name.lower() == 'mav':
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

            elif shop_name.lower() == 'validate':
                validate_shopgames()

            elif shop_name.lower() == 'outdated':
                outs = Game.objects.filter(
                    shop_available=True,
                    shop_saving__gte=0
                ).order_by('-shop_saving', '-hotness').all()[:20]
                for out in outs:
                    out.shop_outdated = True
                    out.save()
                update_outdated_game_shop_prices()

            else:
                raise ValueError(f'Unknown shop name {shop_name}')
        logger.info('cmd done')

    def handle(self, *args, **options):
        try:
            self._main(*args, **options)
        except Exception:
            logger.exception('Error during scraping shops!')
            raise
