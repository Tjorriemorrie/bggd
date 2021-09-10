from django.db.models import Sum, Avg, F

from main.models import Player, GameDay, Day


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
