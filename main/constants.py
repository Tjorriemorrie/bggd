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

REC_MIN_CUTOFF = 8
REC_PLAYER_LIMIT = 250_000

STOCK_IN = 'In Stock'
STOCK_OUT = 'Out of Stock'

SHOP_RARU = 'Raru'
