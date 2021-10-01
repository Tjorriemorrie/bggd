import logging
from time import time
from typing import List

from django.core.management import BaseCommand
from django.db import OperationalError
from django.db.models import Q, F, Max
from retry import retry

from main.errors import PlayerScrapeError, PlayerRatingNewGameError, OutOfTimeError
from main.models import Player, Game
from main.recommendations import predict_player
from main.scraper import scrape_player, scrape_player_ratings
from main.stats import update_gamedays

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape bgg player data'
    timeout = 60 * 60 * 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_at = time()
        self.count = 0
        self.prefix = ''

    def _check_watch(self):
        self.count += 1
        duration = time() - self.start_at
        if duration > self.timeout:
            raise OutOfTimeError()
        else:
            exp = self.timeout / duration * self.count
        self.prefix = f'[{self.count}/{int(exp)}]'

    def _process(self, players: List[Player], game_ids: List[int], keyword: str):
        for player in players:
            self._check_watch()

            # details
            time_int = time()
            try:
                scrape_player(player)
                logger.info(f'scrape_player took {time() - time_int:.1f}s')
            except PlayerScrapeError:
                player.delete()
                logger.info(f'Deleted bad user {player}')
                continue

            # ratings
            time_int = time()
            try:
                scrape_player_ratings(player)
                logger.info(f'scrape_player_ratings took {time() - time_int:.1f}s')
            except PlayerRatingNewGameError:
                pass
            if not player.reviews.count():
                player.delete()
                logger.info(f'Deleted player without ratings {player}')

            else:
                # recommendations
                time_int = time()
                predict_player(player, game_ids)
                logger.info(f'predict_player took {time() - time_int:.1f}s')

                # once player score is updated...
                # update gamedays for reviews
                time_int = time()
                update_gamedays(player)
                logger.info(f'update_gamedays took {time() - time_int:.1f}s')

            logger.info(f'{self.prefix} {keyword} {player}')

    def _loader(self):
        game_ids = Game.objects.values_list('id', flat=True)

        # NEW PLAYERS
        logger.info(''.join(['='] * 99))
        logger.info('Scraping new players...')
        players = Player.objects.filter(
            Q(scraped_at__isnull=True) |
            Q(rec_at__isnull=True)).order_by(
            'created_at').all()[:1_000]
        while players:
            self._process(players, game_ids, 'created')
            players = Player.objects.filter(
                Q(scraped_at__isnull=True) |
                Q(rec_at__isnull=True)).order_by(
                'created_at').all()[:1_000]

        # UPDATED PLAYERS
        logger.info(''.join(['='] * 99))
        logger.info('Updating new data on scraped players...')
        players = Player.objects.annotate(
            last_review=Max('reviews__reviewed_at')).filter(
            Q(rec_at__isnull=False) &
            Q(last_review__gt=F('rec_at'))).order_by(
            'rec_at').all()[:1_000]
        while players:
            self._process(players, game_ids, 'updated')
            players = Player.objects.annotate(
                last_review=Max('reviews__reviewed_at')).filter(
                Q(rec_at__isnull=False) &
                Q(last_review__gt=F('rec_at'))).order_by(
                'rec_at').all()[:1_000]

        # UPKEEPING PLAYERS
        logger.info(''.join(['='] * 99))
        logger.info('Upkeeping old players...')
        players = Player.objects.order_by(
            'scraped_at').all()[:1_000]
        while players:
            self._process(players, game_ids, 'upkeeped')
            players = Player.objects.order_by(
                'scraped_at').all()[:1_000]

        logger.info(''.join(['='] * 50) + ' scraping done ' + ''.join(['='] * 50))

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def handle(self, *args, **options):
        try:
            self._loader()
        except OutOfTimeError:
            logger.info(''.join(['='] * 50) + ' outta time ' + ''.join(['='] * 50))
