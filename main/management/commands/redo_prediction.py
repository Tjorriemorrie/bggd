import logging
from datetime import timedelta
from typing import List

from django.core.management import BaseCommand
from django.utils.timezone import now

from main.models import Player, Game
from main.recommendations import predict_player
from main.scraper import scrape_player_ratings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Redo player prediction'

    def _predict_player(self, game_ids: List[int], player: Player):
        predict_player(player, game_ids)
        player.redo_requested_at = None
        player.redo_completed_at = now()
        player.save()
        logger.info(f'Predicting for player {player} done')

    def _load_next_player(self):
        # logger.info('Searching for player...')
        one_day_ago = now() - timedelta(days=1)
        player = Player.objects.filter(
            redo_requested_at__isnull=False
        ).exclude(
            redo_started_at__gt=one_day_ago
        ).first()
        if player:
            player.redo_started_at = now()
            player.redo_completed_at = None
            player.save()
        return player

    def handle(self, *args, **options):
        player = self._load_next_player()
        if not player:
            logger.info('No player requested redo')
            return

        # first refresh ratings
        scrape_player_ratings(player)

        # then redo prediction
        game_ids = Game.objects.values_list('id', flat=True)
        self._predict_player(game_ids, player)
