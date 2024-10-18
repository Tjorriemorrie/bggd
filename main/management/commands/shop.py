import logging
import time

from django.core.management import BaseCommand
from django.utils import timezone

from main.models import Scrapelog
from main.selectors import get_today
from main.shops import shop_names, shop_scrapers

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape shops'

    def add_arguments(self, parser):
        """Add shop name."""
        parser.add_argument('shop_name', type=str, help='Name of shop to scrape')

    def handle(self, *args, **options):
        """Scrape shops."""
        logger.info('Scraping shops...')
        time.sleep(3)

        name_param = options['shop_name']
        names = shop_names if name_param == 'all' else [name_param]

        for name in names:
            msg = 'OK'
            start_at = time.time()
            try:
                shop_scraper = shop_scrapers[name]
                shop_scraper()
            except Exception as exc:
                logger.exception(f'Problem scraping {name}')
                msg = str(exc).strip()
            dur = round(time.time() - start_at)
            today = get_today()
            scrapelog, created = Scrapelog.objects.update_or_create(
                day=today,
                target=f'shop {name}',
                defaults={
                    'scraped_at': timezone.now(),
                    'outcome': msg,
                    'duration': dur,
                },
            )
            logger.info(f'{"Created" if created else "Updated"} {scrapelog}')
