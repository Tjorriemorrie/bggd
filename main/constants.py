from datetime import datetime
from itertools import product

from django.utils.timezone import make_aware

START_GAME_OF_THE = make_aware(datetime(2006, 1, 1))

WEIGHT_HEAVY = 'Heavy'
WEIGHT_MEDIUM = 'Medium'
WEIGHT_LIGHT = 'Light'
WEIGHTS = (WEIGHT_LIGHT, WEIGHT_MEDIUM, WEIGHT_HEAVY)

PLAYERS_SIZES = (1, 2, 3, 4)
REC_COMBOS = set(product(WEIGHTS, PLAYERS_SIZES))

REC_MIN_CUTOFF = 3
REC_PLAYER_LIMIT = 170_000

AVAIL_OUT_OF_STOCK = 'Out of Stock'
AVAIL_7_TO_10 = '7 to 10'
