import logging

from django.core.management import CommandError
from django.core.management.base import BaseCommand

from main.models import Game, Listing
from main.shops import shop_hosts
from main.shops.helpers import update_listing_with_price

logger = logging.getLogger(__name__)


def fix_urls():
    """Fix listings with relative URLs."""
    listings = Listing.objects.exclude(url__startswith='http').all()

    logger.info(f'Found {len(listings)} listings with bad URLs')

    for listing in listings:
        slash = '' if listing.url.startswith('/') else '/'
        new_url = shop_hosts[listing.shop.name] + slash + listing.url
        logger.info(f'{listing.url} --> {new_url}')
        listing.url = new_url
        listing.save()


def fix_prices():
    """Dummy price fixer function."""
    logger.info('Running fix_prices...')
    listings = Listing.objects.all()
    total = len(listings)
    logger.info(f'Found {total} listings')
    for ix, listing in enumerate(listings):
        last_price = listing.prices.last()
        if listing.price != last_price.price or listing.in_stock != last_price.in_stock:
            logger.info(f'{ix}/{total}: Fixing {listing}')
            update_listing_with_price(listing, last_price)
        else:
            logger.info(f'{ix}/{total}: Correct {listing}')

    games = Game.objects.filter(shop_outdated=True).all()
    total = len(games)
    logger.info(f'Found {total} games')
    for ix, game in enumerate(games):
        logger.info(f'{ix}/{total}: Fixing {game}')


class Command(BaseCommand):
    help = 'Fix various data inconsistencies with subcommands like "urls" or "prices"'

    def add_arguments(self, parser):
        """Args for command."""
        subparsers = parser.add_subparsers(dest='subcommand', help='Subcommand to run')

        # Subcommand: urls
        subparsers.add_parser('urls', help='Fix URLs in listings')

        # Subcommand: prices
        subparsers.add_parser('prices', help='Fix prices in listings')

    def handle(self, *args, **options):
        """Run cmd."""
        subcommand = options.get('subcommand')
        if subcommand == 'urls':
            fix_urls()
        elif subcommand == 'prices':
            fix_prices()
        else:
            raise CommandError('You must specify a valid subcommand: "urls" or "prices"')
