import logging

from django.core.management import BaseCommand

from main.recommendations import train_model

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train surprise model on data'

    def handle(self, *args, **options):
        train_model()
