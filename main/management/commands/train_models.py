import logging
import time

from django.core.management import BaseCommand

from main.models import CronSchedule
from main.recommendations import train_rec_model, train_sim_model

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train surprise model on data'

    def add_arguments(self, parser):
        """Args for which model."""
        parser.add_argument('name', type=str)

    def handle(self, *args, **options):
        """Train models."""
        logger.info(''.join(['='] * 99))
        msg = 'OK'
        start_at = time.time()
        try:
            if options['name'] == 'sim':
                train_sim_model()
            elif options['name'] == 'rec':
                train_rec_model()
        except Exception as exc:
            msg = str(exc)
        dur = time.time() - start_at
        if options['name'] == 'sim':
            CronSchedule.upart(
                {
                    'train_models_sim': msg,
                    'train_models_sim_dur': round(dur / 60, 1),
                }
            )
