import logging
from datetime import timedelta
from typing import List

from django.core.management import BaseCommand
from django.db.models import Q, F, Max
from django.utils.timezone import now

from main.errors import PlayerScrapeError, PlayerRatingNewGameError
from main.models import Player, Game
from main.recommendations import predict_player
from main.scraper import scrape_player, scrape_player_ratings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape bgg player data'

    def _process(
            self, players: List[Player], game_ids: List[int], keyword: str,
            total: int, start_at: int):
        for ix, player in enumerate(players):
            try:
                scrape_player(player)
            except PlayerScrapeError:
                player.delete()
                logger.info(f'Deleted bad user {player}')
                continue
            try:
                scrape_player_ratings(player)
            except PlayerRatingNewGameError as exc:
                pass
            if not player.reviews.count():
                player.delete()
                logger.info(f'Deleted player without ratings {player}')
            else:
                predict_player(player, game_ids, top_n=3)
            logger.info(f'{ix + start_at}/{total}: {keyword} {player}')

    def handle(self, *args, **options):
        game_ids = Game.objects.values_list('id', flat=True)
        limit = 7
        total_player_cnt = Player.objects.count()
        daily_cut = total_player_cnt // limit
        running = 0
        total = 0
        remainder = daily_cut - running

        if remainder:
            logger.info(''.join(['='] * 99))
            logger.info('Scraping new players...')
            logger.info(f'Running:{running} daily cut:{daily_cut} remainder:{remainder}')
            players = Player.objects.filter(
                Q(scraped_at__isnull=True) |
                Q(rec_at__isnull=True)).order_by(
                'created_at').all()[:remainder]
            logger.info(f'Found {len(players)} players')
            total += len(players)
            self._process(players, game_ids, 'created', total, running)
            running += len(players)
            remainder = daily_cut - running

        if remainder:
            logger.info(''.join(['='] * 99))
            logger.info('Updating new data on scraped players...')
            logger.info(f'Running:{running} daily cut:{daily_cut} remainder:{remainder}')
            players = Player.objects.annotate(
                last_review=Max('reviews__reviewed_at')).filter(
                Q(rec_at__isnull=False) &
                Q(last_review__gt=F('rec_at'))).order_by(
                'rec_at').all()[:remainder]
            logger.info(f'Found {len(players)} players')
            total += len(players)
            self._process(players, game_ids, 'updated', total, running)
            running += len(players)
            remainder = daily_cut - running

        if remainder:
            logger.info(''.join(['='] * 99))
            logger.info('Upkeeping old players...')
            logger.info(f'Running:{running} daily cut:{daily_cut} remainder:{remainder}')
            upkeep_days = 14
            upkeep_delta = now() - timedelta(days=upkeep_days)
            logger.info(f'Using {upkeep_days} days from {upkeep_delta}')
            players = Player.objects.filter(
                scraped_at__lt=upkeep_delta).order_by(
                'scraped_at').all()[:remainder]
            logger.info(f'Found {len(players)} players')
            total += len(players)
            self._process(players, game_ids, 'upkeeped', total, running)
            running += len(players)
            remainder = daily_cut - running

        logger.info(''.join(['='] * 99))
        logger.info(f'Running:{running} daily cut:{daily_cut} remainder:{remainder}')
        logger.info('Done')
