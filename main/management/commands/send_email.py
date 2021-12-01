import logging

from django.core.mail import send_mail
from django.core.management import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sends email'

    def handle(self, *args, **options):
        logger.info('Sending email...')
        send_mail(
            'Subject test',
            'Basic message',
            'jacoj82@gmail.com',
            ['jacoj82@gmail.com'],
            fail_silently=False,
        )
        logger.info('Email sent.')
