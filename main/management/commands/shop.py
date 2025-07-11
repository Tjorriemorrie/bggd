import logging
import time

from django.core.management import BaseCommand
from django.utils import timezone

from main.models import Scrapelog
from main.selectors import get_today, upsert_shop
from main.shops import shop_enabled, shop_names, shop_scrapers
from main.shops.helpers import missed_listings  # Ensure `shop_enabled` is imported

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape shops'

    def add_arguments(self, parser):
        """Add shop name and optional force flag."""
        parser.add_argument('shop_name', type=str, help='Name of shop to scrape')
        parser.add_argument(
            '--force', action='store_true', help='Force run even if shop is disabled'
        )

    def handle(self, *args, **options):
        """Scrape shops."""
        logger.info('Scraping shops...')
        time.sleep(3)

        name_param = options['shop_name']
        force = options['force']
        names = shop_names if name_param == 'all' else [name_param]

        for name in names:
            msg = 'OK'
            start_at = time.time()
            try:
                shop_scraper = shop_scrapers[name]
                enabled = shop_enabled[name]
                if not enabled and not force:
                    logger.info(f'Skipping disabled shop {name}.')
                    shop = upsert_shop(name)
                    missed_listings(shop)
                    continue
                shop_scraper()
            except Exception as exc:
                logger.exception(f'Problem scraping {name}')
                msg = str(exc).strip() or exc.__class__.__name__
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
