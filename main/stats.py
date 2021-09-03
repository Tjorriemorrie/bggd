from django.db.models import Count

from main.models import Game, Review


def hotness():
    # remove current hotness
    Game.objects.update(hotness=None)
    # aggregate reviews on games for past month
    vals = Review.objects.values('game_id').annotate(
        Count('id').values_list('game_id', 'id__count'))
    a = 1
