import logging
import time

from django.core.management import BaseCommand
from django.db import OperationalError
from retry import retry

from main.models import CronSchedule
from main.stats import (
    update_days,
    update_game_of_the_month,
    update_game_of_the_year,
    update_gamedays,
    update_hotness,
    update_weights,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update game hotness'

    @retry(OperationalError, delay=3, jitter=3, max_delay=30)
    def handle(self, *args, **options):
        """Run update game stats."""
        logger.info('Updating reviews into daily stats!')
        msg = 'OK'
        start_at = time.time()
        try:
            logger.info(''.join(['='] * 99))
            update_gamedays()

            logger.info(''.join(['='] * 99))
            update_days()

            logger.info(''.join(['='] * 99))
            update_hotness()

            logger.info(''.join(['='] * 99))
            update_weights()

            logger.info(''.join(['='] * 99))
            update_game_of_the_month()

            logger.info(''.join(['='] * 99))
            update_game_of_the_year()
        except Exception as exc:
            msg = str(exc)
        dur = time.time() - start_at
        CronSchedule.upart(
            {
                'update_game_stats': msg,
                'update_game_stats_dur': round(dur / 60, 1),
            }
        )
