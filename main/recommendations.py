import logging
import pickle
from contextlib import suppress
from datetime import timedelta
from operator import itemgetter
from pathlib import Path

import numpy as np
import pandas as pd
from django.db import OperationalError
from django.utils.timezone import now
from retry import retry
from scipy import stats
from sklearn.metrics.pairwise import cosine_similarity
from sortedcontainers import SortedDict, SortedList
from surprise import SVD, AlgoBase, Dataset, Reader, dump

from bgg.settings import BASE_DIR
from main.constants import (
    IGNORE_FAMILIES,
    LABEL_CATEGORY,
    LABEL_FAMILY,
    REC_MAX_CUTOFF,
    REC_MIN_CUTOFF,
    SOME_YEARS_AGO,
)
from main.errors import PlayerRatingNewGameError, PlayerRatingUsernameNotFoundError
from main.games import scrape_player_ratings
from main.models import LABEL_MECHANIC, Game, Label, Player, Rec, Review

logger = logging.getLogger(__name__)

FILE_REC_MODEL = BASE_DIR / 'model.dmp'
FILE_SIM_MODEL = BASE_DIR / 'model_sim.dmp'

_rec_algo = None
_sim_algo = None


def get_rec_algo() -> AlgoBase:
    """Get recommendation model."""
    global _rec_algo
    if not _rec_algo:
        logger.info('loading recommendation algorithm...')
        _rec_algo, _ = dump.load(FILE_REC_MODEL)
        logger.info(f'loaded {_rec_algo}')
    return _rec_algo


def get_sim_algo() -> AlgoBase:
    """Get similar model."""
    global _sim_algo  # noqa PLW0603
    if not _sim_algo:
        logger.info('loading similarity algorithm...')
        with Path.open(FILE_SIM_MODEL, 'r+b') as fp:
            _sim_algo = pickle.load(fp)  # noqa S301
        logger.info('loaded')
    return _sim_algo


def train_rec_model():
    """Train recommendation model."""
    logger.info('Training recommendations model...')

    logger.info(
        f'Loading players (min {REC_MIN_CUTOFF} to max {REC_MAX_CUTOFF} ratings per player)...'
    )
    player_ids = Player.objects.filter(
        reviews_cnt__gte=REC_MIN_CUTOFF, reviews_cnt__lte=REC_MAX_CUTOFF
    ).values_list('id', flat=True)

    logger.info(f'Loading the reviews from the {len(player_ids):,} players found.')
    values = Review.objects.filter(player__in=player_ids).values_list(
        'player_id', 'game_id', 'rating'
    )
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


def load_next_and_predict():
    """Load next player to predict."""
    ten_min_ago = now() - timedelta(minutes=10)
    player = (
        Player.objects.filter(redo_requested_at__isnull=False)
        .exclude(redo_started_at__gt=ten_min_ago)
        .first()
    )
    if not player:
        logger.info('No player requested prediction redo')
        return
    player.redo_started_at = now()
    player.redo_completed_at = None
    player.save()

    # first refresh ratings
    logger.info(f'Refreshing ratings for {player}')
    with suppress(TypeError, KeyError, PlayerRatingNewGameError, PlayerRatingUsernameNotFoundError):
        scrape_player_ratings(player)

    # then redo prediction
    game_ids = Game.objects.values_list('id', flat=True)
    predict_player(player, game_ids)
    player.redo_requested_at = None
    player.redo_completed_at = now()
    player.save()
    logger.info(f'Finished predicting for {player}')


@retry(OperationalError, delay=3, jitter=3, max_delay=30)
def predict_player(player: Player, game_ids: list[id]) -> list[tuple[float, int]] | None:
    """Predict games for player."""
    logger.info(f'Predicting for {player}')
    algo = get_rec_algo()
    reviews = player.reviews.all()
    player.reviews_cnt = len(reviews)
    player.last_review_at = max([r.reviewed_at for r in reviews]) if reviews else None
    player.rec_at = now()
    player.reviews_scr = None

    # clear player recs, to remove games out of stock in spots not getting replaced.
    Rec.objects.filter(player=player).delete()

    if player.reviews_cnt < 3:  # noqa PLR2004
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
        # always skip if game is more than some years old
        if game.year <= SOME_YEARS_AGO:
            continue
        Rec.objects.create(
            game=game,
            player=player,
            predicted=val,
            rec_at=now(),
            is_primary=bool(cnt == 0),
            weight_tag=game.weight_tag,
            best_players=cnt,
        )
        cnt += 1
        if cnt >= 10:  # noqa PLR2004
            break

    # score player
    ratings = SortedList([r.rating for r in reviews])
    spaces = np.linspace(1, 10, num=len(ratings))
    slope, intercept, r_value, p_value, std_err = stats.linregress(spaces, ratings)
    player.reviews_scr = slope * 10
    logger.info(f'{player} reviews score: {player.reviews_scr}')

    player.save()
    return top_recs


def train_sim_model():
    """Train similar games model."""
    logger.info('Training similarity model on value...')

    # logger.info('Clearing existing groupings...')
    # Game.objects.update(sim_cluster=None)

    mechanics = Label.objects.filter(type=LABEL_MECHANIC).all()
    logger.info(f'Loaded {len(mechanics)} mechanics')
    categories = Label.objects.filter(type=LABEL_CATEGORY).all()
    logger.info(f'Loaded {len(categories)} categories')
    families = Label.objects.filter(type=LABEL_FAMILY).all()
    families = [f for f in families if not any(ig in f.shop_name for ig in IGNORE_FAMILIES)]
    logger.info(f'Loaded {len(families)} families')

    games = (
        Game.objects.prefetch_related('mechanics', 'families', 'categories')
        .exclude(scraped_at__isnull=True)
        .all()
    )
    logger.info(f'Loaded {len(games)} games')

    logger.info('Building dataset...')
    data = []
    for game in games:
        mec_flags = [m in game.mechanics.all() and 0.7 for m in mechanics]
        cat_flags = [m in game.categories.all() and 0.2 for m in categories]
        fam_flags = [m in game.families.all() and 0.4 for m in families]
        try:
            weight_flags = [game.weight_avg / 5]
        except TypeError:
            weight_flags = [5]
        row = mec_flags + cat_flags + fam_flags + weight_flags
        data.append(row)

    # CONTENT_BASED RECOMMENDATION WITH COSINE SIMILARITY VECTORS
    logger.info(f'Calculating cosine similarity on {len(data)} dataset...')
    cos_sim_mtx = cosine_similarity(data, data)
    avgs_at_co = [
        sorted(list(enumerate(r)), key=itemgetter(1), reverse=True)[7][1] for r in cos_sim_mtx
    ]
    avg_at_co = sum(avgs_at_co) / len(avgs_at_co)
    logger.info(f'Avg score for 5 sims is {avg_at_co}')

    logger.info('Updating games...')
    today = now()
    for game_ix, game in enumerate(games):
        scores = list(enumerate(cos_sim_mtx[game_ix]))
        scores_sorted = sorted(scores, key=itemgetter(1), reverse=True)
        sim_games = []
        for score_ix, score in scores_sorted:
            if len(sim_games) >= 3 and score < avg_at_co:  # noqa PLR2004
                break
            if len(sim_games) >= 9:  # noqa PLR2004
                break
            sim_game = games[score_ix]
            if sim_game == game:
                continue
            if sim_game.year > SOME_YEARS_AGO:
                sim_games.append(sim_game)
        game.similars.set(sim_games)
        game.sim_at = today
        game.save()
