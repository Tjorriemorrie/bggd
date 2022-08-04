import logging
from time import time

from django.core.management import BaseCommand

from main.recommendations import train_rec_model, train_mec_model

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train surprise model on data'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str)

    def handle(self, *args, **options):
        start = time()

        if options['name'] == 'mec':
            train_mec_model()
        elif options['name'] == 'rec':
            train_rec_model()

        mins = (time() - start) // 60
        logger.info(f'Total training time took {mins} mins.')

        logger.info(''.join(['='] * 50) + ' done ' + ''.join(['='] * 50))
