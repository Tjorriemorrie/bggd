import codecs
import logging
import sys

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    # def ready(self):
        # if sys.stdout.encoding != 'cp850':
        #     sys.stdout = codecs.getwriter('cp850')(sys.stdout.buffer, 'strict')
        # if sys.stderr.encoding != 'cp850':
        #     sys.stderr = codecs.getwriter('cp850')(sys.stderr.buffer, 'strict')

    #     logger.info(f'sys argv: {sys.argv}')
    #     if any(['gunicorn' in a for a in sys.argv]):
    #         from main.recommendations import get_rec_algo
    #         get_rec_algo()
