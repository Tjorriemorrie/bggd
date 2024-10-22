import logging

from django.core.management import BaseCommand

from main.models import Listing
from main.shops import shop_hosts

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix something'

    def handle(self, *args, **options):
        """Fix stuff."""
        listings = Listing.objects.exclude(url__startswith='http').all()

        logger.info(f'Found {len(listings)} with bad urls')

        for listing in listings:
            slash = '' if listing.url.startswith('/') else '/'
            new_url = shop_hosts[listing.shop.name] + slash + listing.url
            logger.info(f'{listing.url} --> {new_url}')
            listing.url = new_url
            listing.save()
