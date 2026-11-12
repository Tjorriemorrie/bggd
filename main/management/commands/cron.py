import logging
import time

from django.core.management import BaseCommand, CommandError, call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cronjob'

    def handle(self, *args, **options):
        """Run cron job; failed shop scrapes fail the run once the bgg steps are done."""
        logger.info('⏰' + ' starting cron job '.center(99, '*'))
        time.sleep(1)

        logger.info('⏰' + ' scraping shops '.center(99, '*'))
        shop_error = None
        try:
            call_command('shop', 'all')
        except CommandError as exc:
            # The bgg steps refresh the prices shown for every shop that did scrape, so
            # one failed shop must not hold them back.
            logger.error(f'❌ Shop scraping failed, carrying on with the bgg steps: {exc}')
            shop_error = exc

        logger.info('⏰' + ' scraping bgg auto '.center(99, '*'))
        call_command('game', 'auto')

        logger.info('⏰' + ' scraping bgg ids '.center(99, '*'))
        call_command('game', 'new')

        logger.info('⏰' + ' updating game values '.center(99, '*'))
        call_command('game', 'out')

        logger.info('⏰' + ' clean games '.center(99, '*'))
        call_command('game', 'clean')

        if shop_error:
            logger.error(f'❌ Cron job finished with failed shops: {shop_error}')
            raise CommandError(f'Cron job finished with failed shops: {shop_error}') from shop_error
        logger.info('⏰' + ' finished cron job '.center(99, '*'))
