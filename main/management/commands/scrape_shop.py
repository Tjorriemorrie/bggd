import logging
import time

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
from main.models import CronSchedule, Game, Shop
from main.shops import scrape_site, update_outdated_game_shop_prices, validate_shopgames

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape shops'

    def add_arguments(self, parser):
        """Add shop name."""
        parser.add_argument('shop_name', nargs='+', type=str)
        parser.add_argument('--fail_fast', action='store_true')

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def _main(self, shop_name, fail_fast):  # noqa PLR0912
        logger.info(''.join(['='] * 99))
        if shop_name.lower() == 'mav':
            shop = Shop.objects.get(name=SHOP_MEEPS_AND_VEEPS)
            scrape_site(shop, fail_fast=fail_fast)
        elif shop_name.lower() == 'tl':
            shop = Shop.objects.get(name=SHOP_TIMELESS)
            scrape_site(shop, fail_fast=fail_fast)
        elif shop_name.lower() == 'gh':
            shop = Shop.objects.get(name=SHOP_GEEKHOME)
            scrape_site(shop, fail_fast=fail_fast)
        elif shop_name.lower() == 'thd':
            shop = Shop.objects.get(name=SHOP_THD)
            scrape_site(shop, fail_fast=fail_fast)
        elif shop_name.lower() == 'ttg':
            shop = Shop.objects.get(name=SHOP_TTG)
            scrape_site(shop, fail_fast=fail_fast)
        elif shop_name.lower() == 'gg':
            shop = Shop.objects.get(name=SHOP_GARGOYLE)
            scrape_site(shop, fail_fast=fail_fast)
        elif shop_name.lower() == 'sab':
            shop = Shop.objects.get(name=SHOP_SWORD_AND_BOARD)
            scrape_site(shop, fail_fast=fail_fast)
        elif shop_name.lower() == 'lu':
            shop = Shop.objects.get(name=SHOP_LEVEL_UP)
            scrape_site(shop, fail_fast=fail_fast)
        elif shop_name.lower() == 'amz':
            shop = Shop.objects.get(name=SHOP_AMAZON)
            scrape_site(shop, fail_fast=fail_fast)
        elif shop_name.lower() == 'bgbsa':
            shop = Shop.objects.get(name=SHOP_BGBSA)
            scrape_site(shop, fail_fast=fail_fast)

        elif shop_name.lower() == 'validate':
            validate_shopgames()

        elif shop_name.lower() == 'out':
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

    def handle(self, *args, **options):
        """Scrape shops."""
        shop_names = options['shop_name']
        for shop_name in shop_names:
            msg = 'OK'
            start_at = time.time()
            try:
                self._main(shop_name, options.get('fail_fast'))
            except Exception as exc:
                msg = str(exc)
            dur = time.time() - start_at
            CronSchedule.upart(
                {
                    f'scrape_shop_{shop_name}': msg,
                    f'scrape_shop_{shop_name}_dur': round(dur / 60, 1),
                }
            )
