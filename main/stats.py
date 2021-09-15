import logging
from datetime import timedelta

from django.db.models import Sum, Avg, F, Q
from django.utils.timezone import now
import numpy as np
from main.models import Player, GameDay, Day, Game

logger = logging.getLogger(__name__)


def update_gamedays(player: Player):
    if player.reviews_scr is None:
        return

    outdated_days = set()
    outdated_gamedays = set()

    for review in player.reviews.all():
        adj_rating = review.rating * (player.reviews_scr / 10)

        # create to set review's gameday
        day, day_created = Day.objects.get_or_create(
            day=review.day,
            defaults={
                'reviews_cnt': 1,
                'reviews_avg': review.rating,
                'reviews_adj': adj_rating,
                'last_review_id': review.id,
                'last_review_update': review.updated_at})
        gameday, gameday_created = GameDay.objects.get_or_create(
            game=review.game,
            day=day,
            defaults={
                'reviews_cnt': 1,
                'reviews_avg': review.rating,
                'reviews_adj': adj_rating})
        review.gameday = gameday
        review.save()

        # reverse update stats for the day
        if not gameday_created:
            outdated_gamedays.add(gameday)
        if not day_created:
            day.last_review_id = review.id
            day.last_review_update = review.updated_at
            outdated_days.add(day)

    # update outdated gamedays
    for gameday in outdated_gamedays:
        gameday.reviews_cnt = gameday.reviews.count()
        gameday.reviews_avg = gameday.reviews.aggregate(
            avg_rating=Avg('rating'))['avg_rating']
        gameday.reviews_adj = gameday.reviews.aggregate(
            adj_rating=Avg(F('rating') * F('player__reviews_scr')))['adj_rating']
        gameday.save()

    # update days in one go
    for day in outdated_days:
        day.reviews_cnt = day.gamedays.aggregate(Sum('reviews_cnt'))['reviews_cnt__sum']
        day.reviews_avg = day.gamedays.aggregate(Avg('reviews_avg'))['reviews_avg__avg']
        day.reviews_adj = day.gamedays.aggregate(Avg('reviews_adj'))['reviews_adj__avg']
        day.save()


def update_hotness():
    logger.info('Updating hotness...')
    one_month = now() - timedelta(days=30)
    gamedays_one_month = GameDay.objects.filter(
        day__day__gte=one_month).order_by('game').values('game').annotate(
        score=Sum(F('reviews_cnt') * F('reviews_adj')))
    for info in gamedays_one_month:
        game = Game.objects.get(id=info['game'])
        game.hotness = info['score']
        game.save()


def update_weights():
    weights = Game.objects.filter(weight_avg__isnull=False).values_list('weight_avg', flat=True)
    weights = np.array(weights)
    cuts = np.percentile(weights, [33, 66])
    logger.info(f'Updating weights between {cuts[0]:.2f} and {cuts[1]:.2f}')
    Game.objects.filter(
        Q(weight_avg__isnull=False) &
        Q(weight_avg__lt=cuts[0])
    ).update(weight_tag='Light')
    Game.objects.filter(
        Q(weight_avg__isnull=False) &
        Q(weight_avg__gt=cuts[1])
    ).update(weight_tag='Heavy')
    Game.objects.filter(
        Q(weight_avg__isnull=False) &
        Q(weight_avg__gte=cuts[0]) &
        Q(weight_avg__lte=cuts[1])
    ).update(weight_tag='Medium')
