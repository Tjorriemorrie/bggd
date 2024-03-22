import logging
from calendar import SUNDAY
from datetime import timedelta

from django.core.management import BaseCommand
from django.db import OperationalError
from django.utils.timezone import now
from retry import retry

from main.models import Game
from main.scraper import scrape_game, scrape_rankings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape bgg for data'

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def _main(self, *args, **options):
        # one_day_ago = now() - timedelta(hours=30)
        days_ago = 5
        total_game_cnt = Game.objects.count()
        daily_cut = total_game_cnt // days_ago

        # logger.info(''.join(['='] * 99))
        # logger.info('Updating top 10 hotness for home page...')
        # games = Game.objects.order_by('-hotness').all()[:10]
        # for ix, game in enumerate(games):
        #     logger.info(f'Progress {ix}/{len(games)}')
        #     if game.updated_at < one_day_ago:
        #         scrape_game(game)

        logger.info(''.join(['='] * 99))
        logger.info('Updating already scraped games...')
        time_ago = now() - timedelta(days=days_ago)
        games = Game.objects.filter(scraped_at__lt=time_ago).all()[:daily_cut]
        for ix, game in enumerate(games):
            logger.info(f'Progress {ix}/{len(games)}')
            scrape_game(game)

        logger.info(''.join(['='] * 99))
        logger.info('Scraping new games...')
        games = Game.objects.filter(scraped_at__isnull=True).all()
        for ix, game in enumerate(games):
            logger.info(f'Progress {ix}/{len(games)}')
            scrape_game(game)

        if now().weekday() == SUNDAY:
            logger.info(''.join(['='] * 99))
            logger.info('No more new games, will scrape for next one...')
            scrape_rankings()

        logger.info(''.join(['='] * 50) + ' scraping done ' + ''.join(['='] * 50))

    def handle(self, *args, **options):
        """Run the scraping games command."""
        try:
            self._main(*args, **options)
        except Exception:
            logger.exception('Error during scraping games!')
            raise
