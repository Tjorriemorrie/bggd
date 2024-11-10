import logging
import time

from django.core.management import BaseCommand, call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cronjob'

    def handle(self, *args, **options):
        """Run cron job."""
        logger.info(' starting cron job '.center(99, '*'))
        time.sleep(1)

        logger.info(' scraping shops '.center(99, '*'))
        call_command('shop', 'all')

        logger.info(' scraping bgg auto '.center(99, '*'))
        call_command('game', 'auto')

        logger.info(' scraping bgg ids '.center(99, '*'))
        call_command('game', 'new')

        logger.info(' updating game values '.center(99, '*'))
        call_command('game', 'out')

        logger.info(' clean games '.center(99, '*'))
        call_command('game', 'clean')

        logger.info(' finished cron job '.center(99, '*'))
