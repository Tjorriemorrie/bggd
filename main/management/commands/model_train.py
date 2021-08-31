import logging

from django.core.management import BaseCommand

from main.recommendations import train_model

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train lightFM model on data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-upkeep',
            action='store_true',
            help='Skip data upkeep')

    def handle(self, *args, **options):
        train_model(skip_upkeep=options['skip_upkeep'])
