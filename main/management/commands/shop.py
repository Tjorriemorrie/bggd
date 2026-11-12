import logging
import time

from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from main.constants import SCRAPE_OK
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
        """Scrape shops, logging each outcome, then fail if any shop failed."""
        logger.info('🛒 Scraping shops...')
        time.sleep(3)

        name_param = options['shop_name']
        force = options['force']
        names = shop_names if name_param == 'all' else [name_param]

        failed = []
        for name in names:
            msg = SCRAPE_OK
            start_at = time.time()
            try:
                shop_scraper = shop_scrapers[name]
                enabled = shop_enabled[name]
                if not enabled and not force:
                    logger.info(f'🛒 Skipping disabled shop {name}.')
                    shop = upsert_shop(name)
                    missed_listings(shop)
                    continue
                shop_scraper()
            except Exception as exc:
                logger.exception(f'❌ Problem scraping {name}')
                msg = str(exc).strip() or exc.__class__.__name__
                failed.append(name)
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
            logger.info(f'🛒 {"Created" if created else "Updated"} {scrapelog}: outcome={msg}')

        # Every shop still gets its turn above; it is the run that fails, so a failed
        # scrape cannot pass for a finished one.
        if failed:
            logger.error(
                f'❌ Shop scrapes failed: failed={len(failed)}, total={len(names)}, shops={failed}'
            )
            raise CommandError(
                f'Failed to scrape {len(failed)} of {len(names)} shops: {", ".join(failed)}'
            )
        logger.info(f'✅ Scraped shops: total={len(names)}')
