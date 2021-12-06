import logging
import pickle
from copy import copy
from typing import Tuple, List, Optional

import numpy as np
import pandas as pd
from django.db import OperationalError
from django.utils.timezone import now
from retry import retry
from sklearn.cluster import KMeans
from sortedcontainers import SortedDict, SortedList
from surprise import Reader, Dataset, SVD, AlgoBase

from bgg.settings import BASE_DIR
from main.constants import REC_COMBOS, PLAYERS_SIZES, REC_MIN_CUTOFF
from main.models import Review, Player, Game, Rec, Label, LABEL_MECHANIC

logger = logging.getLogger(__name__)

FILE_REC_MODEL = BASE_DIR / 'model.pkl'
FILE_MEC_MODEL = BASE_DIR / 'model_mec.pkl'

_algo = None


def get_rec_algo() -> AlgoBase:
    global _algo
    if not _algo:
        logger.info('loading rec algorithm...')
        with open(FILE_REC_MODEL, 'r+b') as fp:
            _algo = pickle.load(fp)
        logger.info('loaded')
    return _algo


def get_mec_algo() -> AlgoBase:
    global _algo
    if not _algo:
        logger.info('loading rec algorithm...')
        with open(FILE_MEC_MODEL, 'r+b') as fp:
            _algo = pickle.load(fp)
        logger.info('loaded')
    return _algo


def train_rec_model():
    logger.info('Training model...')

    logger.info('Loading data...')
    player_ids = Player.objects.filter(
        reviews_cnt__gte=REC_MIN_CUTOFF).order_by(
        '-reviews_scr').values_list('id', flat=True)[:100_000]
    logger.info(f'Found {len(player_ids)} players with >= {REC_MIN_CUTOFF} ratings')
    values = Review.objects.filter(player__in=player_ids).values_list('player_id', 'game_id', 'rating')
    logger.info(f'Found {len(values)} ratings from those players')
    df = pd.DataFrame(values, columns=('player_id', 'game_id', 'rating'))

    logger.info('Creating dataset...')
    reader = Reader(rating_scale=(1, 10))
    dataset = Dataset.load_from_df(df, reader)

    logger.info('Building training sets...')
    train_set = dataset.build_full_trainset()
    algo = SVD()

    logger.info(f'Fitting dataset to {algo}. This will take 30min...')
    algo.fit(train_set)

    logger.info(f'Saving model to {FILE_REC_MODEL}')
    with open(FILE_REC_MODEL, 'w+b') as fp:
        pickle.dump(algo, fp)


def train_mec_model():
    logger.info('Training mechanic model...')

    logger.info('Loading data...')
    games = Game.objects.all()
    mechanics = Label.objects.filter(type=LABEL_MECHANIC).all()
    logger.info(f'Found {len(games)} games and {len(mechanics)} mechanics')

    data = []
    for game in games:
        game_mecs = game.mechanics.all()
        row = [int(m in game_mecs) for m in mechanics]
        data.append(row)

    logger.info('Training kmeans...')
    km = KMeans()
    km.fit(data)
    y = km.predict(data)

    logger.info('Saving and updating games...')
    for game, cluster in zip(games, y):
        game.mechanic_cluster = cluster
        game.save()


@retry(OperationalError, delay=3, jitter=3, max_delay=30)
def predict_player(
        player: Player, game_ids: List[id]) -> Optional[List[Tuple[float, int]]]:
    algo = get_rec_algo()
    reviews = player.reviews.all()
    player.reviews_cnt = len(reviews)
    player.rec_at = now()
    player.reviews_scr = None

    if player.reviews_cnt < 3:
        player.save()
        return

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

    # set/overwrite top recs
    top_recs = list(reversed(sc.items()))
    rec_combos = copy(REC_COMBOS)
    is_primary = True
    for val, game_id in top_recs:
        game = Game.objects.get(id=game_id)
        if not game.best_min_players or not game.best_max_players:
            # logger.info(f'Skipping {game} for not having best players scraped.')
            continue
        for cur_best_players in range(game.best_min_players, game.best_max_players + 1):
            best_players = cur_best_players if cur_best_players in PLAYERS_SIZES else 4
            game_combo = (game.weight_tag, best_players)
            if game_combo in rec_combos:
                break
        else:
            # logger.info(
            #     f'Skipping {game} due to all combos taken: '
            #     f'{game.weight_tag} {game.best_min_players}-{game.best_max_players}')
            continue
        rec, _ = Rec.objects.get_or_create(
            player=player,
            weight_tag=game.weight_tag,
            best_players=best_players)
        if rec.game != game or rec.is_primary != is_primary or rec.predicted != val:
            rec.game = game
            rec.is_primary = is_primary
            rec.predicted = val
            rec.rec_at = now()
            rec.save()
        is_primary = False
        rec_combos.remove(game_combo)
        if not rec_combos:
            break

    # score player
    ratings = SortedList([r.rating for r in reviews])
    spaces = np.linspace(1, 10, num=len(ratings))
    diffs = [9 - abs(r - s) for r, s in zip(ratings, spaces)]
    player.reviews_scr = (sum(diffs) / (len(ratings) * 9)) * 10

    player.save()
    return top_recs


@retry(OperationalError, delay=3, jitter=3, max_delay=30)
def similar_mechanics(game: Game):
    algo = get_mec_algo()
