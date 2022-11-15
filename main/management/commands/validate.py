import logging

from django.core.management import BaseCommand
from django.db import OperationalError
from retry import retry

from main.shops import validate_shop_mia

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Validate'

    @retry(OperationalError, delay=3, jitter=3, max_delay=30)
    def handle(self, *args, **options):
        logger.info('Validating...')
        validate_shop_mia()
