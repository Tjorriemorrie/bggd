import logging

from django.core.management import BaseCommand

from main.players import scrape_saffas

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape boardgamegeek saffas'

    def add_arguments(self, parser):
        """Add arguments."""
        # subparsers = parser.add_subparsers(
        #     title='sub-commands',
        #     required=True,
        # )
        #
        # hotness_parser = subparsers.add_parser(
        #     'hotness',
        #     help='Scrape hotness.',
        # )
        # hotness_parser.set_defaults(method=self.scrape_hotness)

    def handle(self, *args, **options):
        """Run cmd."""
        logger.info(''.join(['='] * 99))

        scrape_saffas()

        logger.info(''.join(['='] * 99))
