import logging

from django.core.management import BaseCommand

from main.constants import SHOP_RARU
from main.shops import scrape_raru

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape shops'

    def add_arguments(self, parser):
        parser.add_argument('shop_name', nargs='+', type=str)

    def handle(self, *args, **options):
        shop_names = options['shop_name']
        logger.info(f'cmd scraping shops {shop_names}')
        for shop_name in shop_names:
            if shop_name.lower() == SHOP_RARU.lower():
                scrape_raru()
            else:
                raise ValueError(f'Unknown shop name {shop_name}')
        logger.info('cmd done')
