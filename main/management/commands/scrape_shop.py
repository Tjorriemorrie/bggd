import logging

from django.core.management import BaseCommand

from main.shops import scrape_raru

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape shops'

    def add_arguments(self, parser):
        parser.add_argument('shop_name', nargs='+', type=str)

    def handle(self, *args, **options):
        shop_name = options['shop_name']
        logger.info(f'cmd scrape shop {shop_name}')
        scrape_raru()
        logger.info('cmd done')
