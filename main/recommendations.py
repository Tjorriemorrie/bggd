import logging
import pickle
from operator import itemgetter
from typing import Tuple, List, Optional

import numpy as np
import pandas as pd
from django.db import OperationalError
from django.utils.timezone import now
from kneed import KneeLocator
from retry import retry
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sortedcontainers import SortedDict, SortedList
from surprise import Reader, Dataset, SVD, AlgoBase, dump

from bgg.settings import BASE_DIR
from main.constants import REC_MIN_CUTOFF, REC_MAX_CUTOFF, SIM_GROUP_SIZE, \
    LABEL_CATEGORY, LABEL_FAMILY, IGNORE_FAMILIES, SOME_YEARS_AGO
from main.models import Review, Player, Game, Rec, Label, LABEL_MECHANIC

logger = logging.getLogger(__name__)

FILE_REC_MODEL = BASE_DIR / 'model.dmp'
FILE_SIM_MODEL = BASE_DIR / 'model_sim.dmp'

_rec_algo = None
_sim_algo = None


def get_rec_algo() -> AlgoBase:
    global _rec_algo
    if not _rec_algo:
        logger.info('loading recommendation algorithm...')
        _rec_algo, _ = dump.load(FILE_REC_MODEL)
        logger.info(f'loaded {_rec_algo}')
    return _rec_algo


def get_sim_algo() -> AlgoBase:
    global _sim_algo
    if not _sim_algo:
        logger.info('loading similarity algorithm...')
        with open(FILE_SIM_MODEL, 'r+b') as fp:
            _sim_algo = pickle.load(fp)
        logger.info('loaded')
    return _sim_algo


def train_rec_model():
    logger.info('Training recommendations model...')

    logger.info(f'Loading players (min {REC_MIN_CUTOFF} to max {REC_MAX_CUTOFF} ratings per player)...')
    player_ids = Player.objects.filter(
        reviews_cnt__gte=REC_MIN_CUTOFF,
        reviews_cnt__lte=REC_MAX_CUTOFF
    ).values_list('id', flat=True)

    logger.info(f'Loading the reviews from the {len(player_ids):,} players found.')
    values = Review.objects.filter(player__in=player_ids).values_list('player_id', 'game_id', 'rating')
    logger.info(f'Found {len(values):,} ratings from those players')

    logger.info('Creating dataset...')
    df = pd.DataFrame(values, columns=('player_id', 'game_id', 'rating'))
    reader = Reader(rating_scale=(1, 10))
    dataset = Dataset.load_from_df(df, reader)

    algo = SVD(verbose=True)

    logger.info('Building full training set...')
    train_set = dataset.build_full_trainset()
    logger.info(f'Fitting dataset to {algo}...')
    algo.fit(train_set)

    # logger.info('cross validating dataset...')
    # res = cross_validate(algo, dataset, n_jobs=1)
    # logger.info(res)

    logger.info(f'Saving model to {FILE_REC_MODEL}')
    dump.dump(FILE_REC_MODEL, algo)


@retry(OperationalError, delay=3, jitter=3, max_delay=30)
def predict_player(
        player: Player, game_ids: List[id]) -> Optional[List[Tuple[float, int]]]:
    algo = get_rec_algo()
    reviews = player.reviews.all()
    player.reviews_cnt = len(reviews)
    player.last_review_at = max([r.reviewed_at for r in reviews]) if reviews else None
    player.rec_at = now()
    player.reviews_scr = None

    # clear player recs, to remove games out of stock in spots not getting replaced.
    Rec.objects.filter(player=player).delete()

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

    top_recs = list(reversed(sc.items()))
    cnt = 0
    for val, game_id in top_recs:
        game = Game.objects.get(id=game_id)
        # skip if cannot buy (only RSA)
        if player.is_rsa() and not game.shop_available or not game.shop_price:
            continue
        # always skip if game is more than 8 years old
        if game.year <= SOME_YEARS_AGO:
            continue
        rec = Rec.objects.create(
            game=game,
            player=player,
            predicted=val,
            rec_at=now(),
            is_primary=bool(cnt == 0),
            weight_tag=game.weight_tag,
            best_players=cnt)
        cnt += 1
        if cnt >= 10:
            break

    # score player
    ratings = SortedList([r.rating for r in reviews])
    spaces = np.linspace(1, 10, num=len(ratings))
    diffs = [9 - abs(r - s) for r, s in zip(ratings, spaces)]
    player.reviews_scr = (sum(diffs) / (len(ratings) * 9)) * 10

    player.save()
    return top_recs


def train_sim_model():
    logger.info('Training similarity model on value...')

    # logger.info('Clearing existing groupings...')
    # Game.objects.update(sim_cluster=None)

    mechanics = Label.objects.filter(type=LABEL_MECHANIC).all()
    logger.info(f'Loaded {len(mechanics)} mechanics')
    categories = Label.objects.filter(type=LABEL_CATEGORY).all()
    logger.info(f'Loaded {len(categories)} categories')
    families = Label.objects.filter(type=LABEL_FAMILY).all()
    families = [
        f for f in families if not
        any(ig in f.name for ig in IGNORE_FAMILIES)]
    logger.info(f'Loaded {len(families)} families')

    games = Game.objects.prefetch_related(
        'mechanics', 'families', 'categories'
    ).exclude(scraped_at__isnull=True).all()
    logger.info(f'Loaded {len(games)} games')

    logger.info('Building dataset...')
    data = []
    for game in games:
        mec_flags = [m in game.mechanics.all() and 0.3 for m in mechanics]
        cat_flags = [m in game.categories.all() and 0.7 for m in categories]
        fam_flags = [m in game.families.all() and 0.5 for m in families]
        weight_flags = [game.weight_avg / 5]
        row = mec_flags + cat_flags + fam_flags + weight_flags
        data.append(row)

    # CONTENT_BASED RECOMMENDATION WITH COSINE SIMILARITY VECTORS
    logger.info(f'Calculating cosine similarity on {len(data)} dataset...')
    cos_sim_mtx = cosine_similarity(data, data)
    avgs_at_co = [
        sorted(list(enumerate(r)), key=itemgetter(1), reverse=True)[7][1]
        for r in cos_sim_mtx]
    avg_at_co = sum(avgs_at_co) / len(avgs_at_co)
    logger.info(f'Avg score for 5 sims is {avg_at_co}')

    logger.info('Updating games...')
    today = now()
    for ix, game in enumerate(games):
        scores = list(enumerate(cos_sim_mtx[ix]))
        scores_sorted = sorted(scores, key=itemgetter(1), reverse=True)
        sim_games = []
        for ix, score in scores_sorted:
            if len(sim_games) >= 3 and score < avg_at_co:
                break
            if len(sim_games) >= 9:
                break
            sim_game = games[ix]
            if sim_game == game:
                continue
            if sim_game.year > SOME_YEARS_AGO:
                sim_games.append(sim_game)
        game.similars.set(sim_games)
        game.sim_at = today
        game.save()


@retry(OperationalError, delay=3, jitter=3, max_delay=30)
def similar_mechanics(game: Game):
    algo = get_sim_algo()
