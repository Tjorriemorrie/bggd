import logging
from datetime import timedelta
from time import time
from typing import List, Dict

from django.core.management import BaseCommand
from django.db.models import Sum, F
from django.utils.timezone import now

from main.errors import OutOfTimeError
from main.models import GameDay, Game

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update game hotness'
    timeout = 60 * 60 * 10

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

    def _process(self, gamedays_one_month: List[Dict[float, int]]):
        for info in gamedays_one_month:
            self._check_watch()
            game = Game.objects.get(id=info['game'])
            game.hotness = info['score']
            game.save()

            # create to set review's gameday
            logger.info(f'{self.prefix} Processed {game}')

    def _loader(self):
        one_month = now() - timedelta(days=30)
        gamedays_one_month = GameDay.objects.filter(
            day__day__gte=one_month).order_by('game').values('game').annotate(
            score=Sum(F('reviews_cnt') * F('reviews_adj')))
        self._process(gamedays_one_month)

    def handle(self, *args, **options):
        logger.info('Updating reviews into daily stats!')
        try:
            self._loader()
        except OutOfTimeError:
            logger.info('Out of time!')
            logger.info(''.join(['='] * 99))
