import logging

from django.core.management import BaseCommand
from django.db import OperationalError
from retry import retry

from main.constants import SHOP_RARU
from main.shops import scrape_raru

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape shops'

    def add_arguments(self, parser):
        parser.add_argument('shop_name', nargs='+', type=str)

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def _main(self, *args, **options):
        shop_names = options['shop_name']
        logger.info(f'cmd scraping shops {shop_names}')
        for shop_name in shop_names:
            if shop_name.lower() == SHOP_RARU.lower():
                scrape_raru()
            else:
                raise ValueError(f'Unknown shop name {shop_name}')
        logger.info('cmd done')

    def handle(self, *args, **options):
        try:
            self._main(*args, **options)
        except Exception:
            logger.exception('Error during scraping shops!')
            raise
