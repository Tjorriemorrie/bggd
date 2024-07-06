import logging
import time

from django.core.management import BaseCommand

from main.models import CronSchedule
from main.scraper import scrape_hotness

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape boardgamegeek hotness'

    def handle(self, *args, **options):
        """Run the scraping games command."""
        logger.info(''.join(['='] * 99))
        msg = 'OK'
        start_at = time.time()
        try:
            scrape_hotness()
        except Exception as exc:
            msg = str(exc)
        dur = time.time() - start_at
        CronSchedule.upart(
            {
                'hotness': msg,
                'hotness_dur': round(dur / 60, 1),
            }
        )
