import logging

from django.core.management import BaseCommand
from django.db import OperationalError
from retry import retry

from main.stats import update_weights, update_hotness, update_game_of_the_month, \
    update_game_of_the_year

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update game hotness'

    @retry(OperationalError, delay=3, jitter=3, max_delay=30)
    def handle(self, *args, **options):
        logger.info('Updating reviews into daily stats!')
        update_hotness()
        update_weights()
        update_game_of_the_month()
        update_game_of_the_year()
