import logging
from datetime import timedelta

from django.core.management import BaseCommand
from django.utils.timezone import now

from main.models import Game
from main.scraper import scrape_game_details, scrape_rankings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape bgg for data'

    def handle(self, *args, **options):

        counter = 0
        limit = 3
        total_game_cnt = Game.objects.count()
        daily_cut = total_game_cnt // limit

        logger.info(''.join(['='] * 99))
        logger.info('Updating already scraped games...')
        time_ago = now() - timedelta(days=limit)
        games = Game.objects.filter(scraped_at__lt=time_ago).all()[:daily_cut]
        for game in games:
            counter += 1
            logger.info(f'Progress {counter}/{daily_cut}')
            scrape_game_details(game)

        logger.info(''.join(['='] * 99))
        logger.info('Scraping new games...')
        games = Game.objects.filter(scraped_at__isnull=True).all()
        for game in games:
            scrape_game_details(game)

        logger.info(''.join(['='] * 99))
        logger.info('No more new games, will scrape for next one...')
        scrape_rankings()

        logger.info(''.join(['='] * 99))
        logger.info('Scraping done')
