import logging
from time import time
from typing import List

from django.core.management import BaseCommand
from django.db.models import Avg, Sum

from main.errors import OutOfTimeError
from main.models import Review, Day, GameDay

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update reviews into daily stats'
    timeout = 60 * 60 * 1

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

    def _process(self, reviews: List[Review]):
        for review in reviews:
            self._check_watch()

            # create to set review's gameday
            day, day_created = Day.objects.get_or_create(
                day=review.day,
                defaults={
                    'reviews_cnt': 1,
                    'reviews_avg': review.rating,
                    'last_review_id': review.id,
                    'last_review_update': review.updated_at})
            gameday, gameday_created = GameDay.objects.get_or_create(
                game=review.game,
                day=day,
                defaults={
                    'reviews_cnt': 1,
                    'reviews_avg': review.rating})
            review.gameday = gameday
            review.save()

            # reverse update stats for the day
            if not gameday_created:
                gameday.reviews_cnt = gameday.reviews.count()
                gameday.reviews_avg = gameday.reviews.aggregate(Avg('rating'))['rating__avg']
                gameday.save()
            if not day_created:
                day.reviews_cnt = day.gamedays.aggregate(Sum('reviews_cnt'))['reviews_cnt__sum']
                day.reviews_avg = day.gamedays.aggregate(Avg('reviews_avg'))['reviews_avg__avg']
                day.last_review_id = review.id
                day.last_review_update = review.updated_at
                day.save()

            # logger.info(f'Processed {review}')
            # logger.info(f'Processed {day}')
            logger.info(f'{self.prefix} Processed {gameday}')

    def _loader(self):
        # first all undayed reviews!
        reviews = Review.objects.filter(
            gameday__isnull=True).order_by(
            'updated_at').all()[:10_000]
        while reviews:
            self._process(reviews)
            reviews = Review.objects.filter(
                gameday__isnull=True).order_by(
                'updated_at').all()[:10_000]

        # raise ValueError('update old')

    def handle(self, *args, **options):
        logger.info('Updating reviews into daily stats!')
        try:
            self._loader()
        except OutOfTimeError:
            logger.info('Out of time!')
            logger.info(''.join(['='] * 99))
