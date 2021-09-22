import logging
import pickle
from typing import Tuple, List

import numpy as np
import pandas as pd
from django.db import OperationalError
from django.utils.timezone import now
from retry import retry
from sortedcontainers import SortedDict, SortedList
from surprise import Reader, Dataset, SVD, AlgoBase

from bgg.settings import BASE_DIR
from main.models import Review, Player, Game

logger = logging.getLogger(__name__)

FILE_MODEL = BASE_DIR / 'model.pkl'

_algo = None


def get_algo() -> AlgoBase:
    global _algo
    if not _algo:
        logger.info('loading algorithm...')
        with open(FILE_MODEL, 'r+b') as fp:
            _algo = pickle.load(fp)
    return _algo


def train_model():
    logger.info('Training model...')

    logger.info('Loading data...')
    player_ids = Player.objects.filter(reviews_cnt__gte=3).values_list('id', flat=True)
    values = Review.objects.filter(player__in=player_ids).values_list('player_id', 'game_id', 'rating')
    df = pd.DataFrame(values, columns=('player_id', 'game_id', 'rating'))

    logger.info('Creating dataset...')
    reader = Reader(rating_scale=(1, 10))
    dataset = Dataset.load_from_df(df, reader)

    logger.info('Building training sets...')
    train_set = dataset.build_full_trainset()
    algo = SVD()

    logger.info(f'Fitting dataset to {algo}')
    algo.fit(train_set)

    logger.info(f'Saving model to {FILE_MODEL}')
    with open(FILE_MODEL, 'w+b') as fp:
        pickle.dump(algo, fp)

    logger.info(f'algorithm fitted on {len(df)}!')


@retry(OperationalError, delay=3, jitter=3, max_delay=30)
def predict_player(
        player: Player, game_ids: List[id], top_n=10
) -> List[Tuple[float, int]]:
    algo = get_algo()
    reviews = player.reviews.all()
    player.reviews_cnt = len(reviews)

    # set predicted on existing reviews
    existing_game_ids = set()
    for review in reviews:
        existing_game_ids.add(review.game.id)
        prediction = algo.predict(player.id, review.game.id, r_ui=review.rating)
        review.predicted = prediction.est
        review.save()

    # get top n recs
    sc = SortedDict()
    other_game_ids = [i for i in game_ids if i not in existing_game_ids]
    for game_id in other_game_ids:
        prediction = algo.predict(player.id, game_id)
        sc[prediction.est] = game_id

    # set top recs
    player.game_recs.clear()
    top_recs = list(reversed(sc.items()))[:top_n]
    for val, game_id in top_recs:
        game = Game.objects.get(id=game_id)
        player.game_recs.add(game)
    player.rec_at = now()

    # score player
    player.reviews_scr = None  # filter used on listing
    if player.reviews_cnt >= 3:
        ratings = SortedList([r.rating for r in reviews])
        spaces = np.linspace(1, 10, num=len(ratings))
        diffs = [9 - abs(r - s) for r, s in zip(ratings, spaces)]
        player.reviews_scr = (sum(diffs) / (len(ratings) * 9)) * 10

    player.save()
    return top_recs
