import logging

logger = logging.getLogger(__name__)


# def outdate_gameday_by_review(review: Review):
#     """Set gameday as outdated to aggregate later in bulk."""
#     if not review.gameday:
#         day, day_created = Day.objects.get_or_create(
#             day=review.day,
#             defaults={
#                 'reviews_cnt': 1,
#                 'reviews_avg': review.rating,
#                 'last_review_id': review.pk,
#                 'last_review_at': review.reviewed_at})
#         gameday, gameday_created = GameDay.objects.get_or_create(
#             game=review.game,
#             day=day,
#             defaults={
#                 'reviews_cnt': 1,
#                 'reviews_avg': review.rating})
#         review.gameday = gameday
#         review.save()
#     review.gameday.is_outdated = True
#     review.gameday.save()
#
#
# def update_gamedays():
#     """Update outdated gamedays and mark days as outdated."""
#     logger.info('Updating gamedays...')
#     gamedays = GameDay.objects.filter(is_outdated=True).all()
#     for gameday in gamedays:
#         gameday.reviews_cnt = gameday.reviews.count()
#         gameday.reviews_avg = gameday.reviews.aggregate(
#             avg_rating=Avg('rating'))['avg_rating']
#         gameday.is_outdated = False
#         try:
#             gameday.save()
#         except IntegrityError as exc:
#             logger.error(f'Deleting bad gameday {gameday.game} {gameday.day}: {exc}')
#             gameday.delete()
#             continue
#         # mark day as outdated
#         gameday.day.is_outdated = True
#         gameday.day.save()
#         logger.info(f'Updated {gameday}')
#
#
# def update_days():
#     """Update outdated days."""
#     logger.info('Updating days...')
#     days = Day.objects.filter(is_outdated=True).all()
#     for day in days:
#         day.reviews_cnt = day.gamedays.aggregate(Sum('reviews_cnt'))['reviews_cnt__sum']
#         day.reviews_avg = day.gamedays.aggregate(Avg('reviews_avg'))['reviews_avg__avg']
#         day.is_outdated = False
#         day.save()
#         logger.info(f'Updated {day}')
#
#
# # DEPRECATED
# def update_gamedays_dep(player: Player):
#     if player.reviews_scr is None:
#         return
#
#     outdated_days = set()
#     outdated_gamedays = set()
#
#     for review in player.reviews.all():
#         # create to set review's gameday
#         day, day_created = Day.objects.get_or_create(
#             day=review.day,
#             defaults={
#                 'reviews_cnt': 1,
#                 'reviews_avg': review.rating,
#                 'last_review_id': review.id,
#                 'last_review_at': review.reviewed_at})
#         gameday, gameday_created = GameDay.objects.get_or_create(
#             game=review.game,
#             day=day,
#             defaults={
#                 'reviews_cnt': 1,
#                 'reviews_avg': review.rating})
#         review.gameday = gameday
#         review.save()
#
#         # reverse update stats for the day
#         if not gameday_created:
#             outdated_gamedays.add(gameday)
#         if not day_created:
#             day.last_review_id = review.id
#             day.last_review_at = review.reviewed_at
#             outdated_days.add(day)
#
#     # update outdated game days
#     for gameday in outdated_gamedays:
#         gameday.reviews_cnt = gameday.reviews.count()
#         gameday.reviews_avg = gameday.reviews.aggregate(
#             avg_rating=Avg('rating'))['avg_rating']
#         gameday.save()
#
#     # update days in one go
#     for day in outdated_days:
#         day.reviews_cnt = day.gamedays.aggregate(Sum('reviews_cnt'))['reviews_cnt__sum']
#         day.reviews_avg = day.gamedays.aggregate(Avg('reviews_avg'))['reviews_avg__avg']
#         day.save()
#
#
# def update_hotness():
#     logger.info('Updating hotness...')
#     one_month = now() - timedelta(days=30)
#     gamedays_one_month = GameDay.objects.filter(
#         day__day__gte=one_month).order_by('game').values('game').annotate(
#         score=Sum(F('reviews_cnt') * F('reviews_avg')))
#     for info in gamedays_one_month:
#         game = Game.objects.get(id=info['game'])
#         game.hotness = info['score']
#         game.save()
#
#
# def update_weights():
#     weights = Game.objects.filter(weight_avg__isnull=False).values_list('weight_avg', flat=True)
#     weights = np.array(weights)
#     cuts = np.percentile(weights, WEIGHTS_CUTOFF)
#     logger.info(f'Updating weights between {cuts}')
#     Game.objects.filter(
#         Q(weight_avg__isnull=False) &
#         Q(weight_avg__lte=cuts[0])
#     ).update(weight_tag=WEIGHT_VERY_LIGHT)
#     Game.objects.filter(
#         Q(weight_avg__isnull=False) &
#         Q(weight_avg__gt=cuts[0]) &
#         Q(weight_avg__lte=cuts[1])
#     ).update(weight_tag=WEIGHT_LIGHT)
#     Game.objects.filter(
#         Q(weight_avg__isnull=False) &
#         Q(weight_avg__gt=cuts[1]) &
#         Q(weight_avg__lte=cuts[2])
#     ).update(weight_tag=WEIGHT_MEDIUM)
#     Game.objects.filter(
#         Q(weight_avg__isnull=False) &
#         Q(weight_avg__gt=cuts[2]) &
#         Q(weight_avg__lte=cuts[3])
#     ).update(weight_tag=WEIGHT_HEAVY)
#     Game.objects.filter(
#         Q(weight_avg__isnull=False) &
#         Q(weight_avg__gt=cuts[3])
#     ).update(weight_tag=WEIGHT_VERY_HEAVY)
#
#
# def go_to_next_month(dt: datetime) -> datetime:
#     dt_copy = copy(dt)
#     current_month = dt.month
#     while dt_copy.month == current_month:
#         dt_copy += timedelta(days=1)
#     return dt_copy
#
#
# def update_game_of_the_month():
#     logger.info('Clearing existing awards...')
#     Award.objects.filter(type=AWARD_GAME_OF_THE_MONTH).delete()
#
#     logger.info('Awarding game of the month!')
#     current_month = START_GAME_OF_THE
#     next_month = go_to_next_month(current_month)
#     used_game_ids = set()
#     while next_month < now():
#         top_games = GameDay.objects.exclude(
#             game_id__in=used_game_ids
#         ).filter(
#             Q(day__day__lt=next_month)
#             & Q(day__day__gte=current_month)
#         ).order_by('game_id').values('game_id').annotate(
#             score=Avg(F('reviews_cnt') * F('reviews_avg')),
#             total_num_ratings=Sum(F('reviews_cnt'))
#         ).order_by('-score').all()[:2]
#         if not top_games:
#             logger.warning(f'No top game for {current_month}')
#         else:
#             top_game = top_games[0]
#             params = {
#                 'game_id': top_game['game_id'],
#                 'score': top_game['score'],
#                 'num_ratings': top_game['total_num_ratings'],
#             }
#             if len(top_games) >= 2:
#                 ru_game = top_games[1]
#                 params.update({
#                     'ru_game_id': ru_game['game_id'],
#                     'ru_score': ru_game['score'],
#                     'ru_num_ratings': ru_game['total_num_ratings'],
#                 })
#             award = Award.objects.create(
#                 type=AWARD_GAME_OF_THE_MONTH,
#                 awarded_at=current_month,
#                 description=f'Game of the Month {current_month:%b \'%y}',
#                 badge=f'{current_month:%b \'%y}',
#                 **params)
#             used_game_ids.add(top_game['game_id'])
#             logger.info(f'{award}')
#
#         current_month, next_month = next_month, go_to_next_month(next_month)
#
#
# def go_to_next_year(dt: datetime) -> datetime:
#     dt_copy = copy(dt)
#     current_year = dt.year
#     while dt_copy.year == current_year:
#         dt_copy += timedelta(days=1)
#     return dt_copy
#
#
# def update_game_of_the_year():
#     logger.info('Awarding game of the year!')
#     logger.info('Clearing existing awards...')
#     Award.objects.filter(type=AWARD_GAME_OF_THE_YEAR).delete()
#     current_year = START_GAME_OF_THE
#     next_year = go_to_next_year(current_year)
#     used_game_ids = set()
#     while next_year < now():
#         top_games = GameDay.objects.exclude(
#             game_id__in=used_game_ids
#         ).filter(
#             Q(day__day__lt=next_year)
#             & Q(day__day__gte=current_year)
#         ).order_by('game_id').values('game_id').annotate(
#             score=Avg(F('reviews_cnt') * F('reviews_avg')),
#             total_num_ratings = Sum(F('reviews_cnt')),
#             total_reviews_avg = Sum(F('reviews_avg'))
#         ).order_by('-score').all()[:2]
#         if not top_games:
#             logger.warning(f'No top game for {current_year}')
#         else:
#             top_game = top_games[0]
#             params = {
#                 'game_id': top_game['game_id'],
#                 'score': top_game['score'],
#                 'num_ratings': top_game['total_num_ratings'],
#             }
#             if len(top_games) >= 2:
#                 ru_game = top_games[1]
#                 params.update({
#                     'ru_game_id': ru_game['game_id'],
#                     'ru_score': ru_game['score'],
#                     'ru_num_ratings': ru_game['total_num_ratings'],
#                 })
#             award = Award.objects.create(
#                 type=AWARD_GAME_OF_THE_YEAR,
#                 awarded_at=current_year,
#                 description=f'Game of the Year {current_year:%Y}',
#                 badge=f'{current_year:%Y}',
#                 **params)
#             used_game_ids.add(top_game['game_id'])
#             logger.info(f'{award}')
#
#         current_year, next_year = next_year, go_to_next_year(next_year)
