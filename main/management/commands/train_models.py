import logging

from django.core.management import BaseCommand

from main.recommendations import train_rec_model, train_mec_model

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train surprise model on data'

    def handle(self, *args, **options):
        train_mec_model()
        train_rec_model()
        logger.info(''.join(['='] * 50) + ' done ' + ''.join(['='] * 50))
