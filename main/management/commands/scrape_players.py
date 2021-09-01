import logging
from typing import List

from django.core.management import BaseCommand
from django.db.models import Q, F, Max

from main.errors import PlayerScrapeError
from main.models import Player, Game
from main.recommendations import predict_player
from main.scraper import scrape_player

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
            predict_player(player, game_ids, top_n=3)
            logger.info(f'{ix + start_at}/{total}: {keyword} {player}')

    def handle(self, *args, **options):
        game_ids = Game.objects.values_list('id', flat=True)
        limit = 7
        total_player_cnt = Player.objects.count()
        daily_cut = total_player_cnt // limit

        logger.info(''.join(['='] * 99))
        logger.info('Updating already scraped players...')
        players = Player.objects.prefetch_related(
            'reviews').annotate(
            last_review=Max('reviews__reviewed_at')).filter(
            Q(rec_at__isnull=False) &
            Q(last_review__gt=F('rec_at'))).order_by(
            'rec_at').all()[:daily_cut]
        logger.info(f'Found {len(players)}')
        self._process(players, game_ids, 'updated', len(players), 0)

        logger.info(''.join(['='] * 99))
        logger.info('Scraping new players...')
        total = Player.objects.filter(
            Q(scraped_at__isnull=True) |
            Q(rec_at__isnull=True)).count()
        logger.info(f'Found {total}')
        if total:
            runn = 0
            batch_size = 1_000
            while True:
                logger.info(f'Batch {runn // batch_size}/{total // batch_size}')
                players = Player.objects.prefetch_related(
                    'reviews').filter(
                    Q(scraped_at__isnull=True) |
                    Q(rec_at__isnull=True)).order_by(
                    'created_at').all()[:batch_size]
                if not players:
                    break
                self._process(players, game_ids, 'created', total, runn)
                runn += batch_size

        logger.info(''.join(['='] * 99))
        logger.info('Done')

