from datetime import datetime
from itertools import product

from django.utils.timezone import make_aware

START_GAME_OF_THE = make_aware(datetime(2006, 1, 1))

WEIGHT_VERY_HEAVY = 'Very Heavy'
WEIGHT_HEAVY = 'Heavy'
WEIGHT_MEDIUM = 'Medium'
WEIGHT_LIGHT = 'Light'
WEIGHT_VERY_LIGHT = 'Very Light'
WEIGHTS = (WEIGHT_VERY_LIGHT, WEIGHT_LIGHT, WEIGHT_MEDIUM, WEIGHT_HEAVY, WEIGHT_VERY_HEAVY)
WEIGHTS_CUTOFF = [15, 38, 62, 85]

PLAYERS_SIZES = (1, 2, 3, 4, 5, 6)
REC_COMBOS = set(product(WEIGHTS, PLAYERS_SIZES))

# memory limits
REC_MIN_CUTOFF = 10
REC_MAX_CUTOFF = 100

STOCK_IN = 'In Stock'
STOCK_OUT = 'Out of Stock'

SHOP_RARU = 'Raru'
SHOP_TAKEALOT = 'Takealot'
SHOP_MEEPS_AND_VEEPS = 'Meeps and Veeps'
SHOP_TIMELESS = 'Timeless'

N_CLUSTERS = 6
