import logging
from time import time
from typing import List

from django.core.management import BaseCommand
from django.db import OperationalError
from django.db.models import Max, F, Q
from django.utils.timezone import now
from retry import retry

from main.errors import PlayerScrapeError, PlayerRatingNewGameError, OutOfTimeError, \
    PlayerRatingUsernameNotFoundError
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

    def _scrape_new_players(self):
        """scrape brand-new players details"""
        logger.info(''.join(['='] * 40) + ' scraping new players ' + ''.join(['='] * 40))
        players = Player.objects.filter(
            scraped_at__isnull=True).order_by(
            'created_at').all()[:1_000]
        while players:
            for player in players:
                self._check_watch()
                # update details
                try:
                    scrape_player(player)
                    logger.info(f'{self.prefix} Scraped details of {player}')
                except PlayerScrapeError:
                    player.delete()
                    logger.info(f'Deleted bad user {player}')
            # renew while
            players = Player.objects.filter(
                scraped_at__isnull=True).order_by(
                'created_at').all()[:1_000]

    def _predict_new_players(self, game_ids: List[int]):
        """give player predictions which does not have any yet"""
        logger.info(''.join(['='] * 40) + ' predicting new players ' + ''.join(['='] * 40))
        players = Player.objects.filter(
            rec_at__isnull=True
        ).order_by('created_at').all()[:1_000]
        while players:
            for player in players:
                self._check_watch()
                predict_player(player, game_ids)
                logger.info(f'{self.prefix} Recommendations for new {player}')
                # update game days (updated from player's reviews)
                update_gamedays(player)
            # renew while
            players = Player.objects.filter(
                rec_at__isnull=True).order_by(
                'created_at').all()[:1_000]

    def _predict_changed_players(self, game_ids: List[int]):
        """update player predictions who have made a new rating"""
        logger.info(''.join(['='] * 40) + ' predicting changed players ' + ''.join(['='] * 40))
        players = Player.objects.prefetch_related('reviews').filter(
            is_outdated=True).all()[:1_000]
        while players:
            for player in players:
                self._check_watch()
                predict_player(player, game_ids)
                logger.info(f'{self.prefix} Recommendations for changed {player}')
                # update game days (updated from player's reviews)
                update_gamedays(player)
                players = Player.objects.prefetch_related('reviews').filter(
                    is_outdated=True).all()[:1_000]

    def _upkeep(self, game_ids: List[int]):
        """upkeep players for remaining time"""
        logger.info(''.join(['='] * 40) + ' upkeeping players ' + ''.join(['='] * 40))
        today = now()
        players = Player.objects.order_by('rec_at').all()[:100]
        while players:
            for player in players:
                self._check_watch()
                days_since = (today - player.rec_at).days

                # details
                try:
                    scrape_player(player)
                except PlayerScrapeError:
                    player.delete()
                    logger.info(f'Deleted bad user {player}')
                    continue

                # upkeep ratings
                try:
                    scrape_player_ratings(player)
                except (TypeError, KeyError,
                        PlayerRatingNewGameError,
                        PlayerRatingUsernameNotFoundError):
                    pass  # stopped at new game

                # dud player?
                if not player.reviews.count():
                    player.delete()
                    logger.info(f'Deleted player without ratings {player}')
                    continue

                # recommendations
                predict_player(player, game_ids)

                # update game days
                # if it is not updated, then bad days with scraping errors will
                # not get fixed, e.g. jul 2022 with very, very low rating counts.
                update_gamedays(player)

                logger.info(f'{self.prefix} upkeeped {player} again after {days_since} days')

            # renew loop
            players = Player.objects.order_by('rec_at').all()[:100]

    @retry((OperationalError,), delay=3, jitter=3, max_delay=30)
    def _loader(self, *args, **options):
        game_ids = Game.objects.values_list('id', flat=True)

        # perform these steps
        self._scrape_new_players()
        self._predict_new_players(game_ids)
        self._predict_changed_players(game_ids)

        # with remaining time
        self._upkeep(game_ids)

    def handle(self, *args, **options):
        try:
            self._loader(*args, **options)
        except OutOfTimeError:
            logger.info(''.join(['='] * 40) + ' outta time ' + ''.join(['='] * 40))
        except Exception:
            logger.exception('Error during scraping players!')
            raise
