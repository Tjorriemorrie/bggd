from datetime import datetime
from itertools import product

from django.utils.timezone import make_aware, now

START_GAME_OF_THE = make_aware(datetime(2006, 1, 1))

LABEL_CATEGORY = 'category'
LABEL_MECHANIC = 'mechanic'
LABEL_FAMILY = 'family'
LABEL_SUBDOMAIN = 'subdomain'

AWARD_GAME_OF_THE_MONTH = 'Game of the month'
AWARD_GAME_OF_THE_YEAR = 'Game of the year'

WEIGHT_VERY_HEAVY = 'Very Heavy'
WEIGHT_HEAVY = 'Heavy'
WEIGHT_MEDIUM = 'Medium'
WEIGHT_LIGHT = 'Light'
WEIGHT_VERY_LIGHT = 'Very Light'
WEIGHTS = (WEIGHT_VERY_LIGHT, WEIGHT_LIGHT, WEIGHT_MEDIUM, WEIGHT_HEAVY, WEIGHT_VERY_HEAVY)
WEIGHTS_CUTOFF = [15, 38, 62, 85]

PLAYERS_SIZES = (1, 2, 3, 4, 5, 6)
REC_COMBOS = set(product(WEIGHTS, PLAYERS_SIZES))

# aug 2022
# 10/200 gives 1-cloudspire 2-paxren
# 11/180 1-nemesis 2-bloodborne 9-cloudspire
# 9/220 1-onmars 2-trickerion 4-bloodborne
# 12/240 1-cloudspire 2-paxren 7-onmars
# 10/190 1-imperiumclassics 2-swarmada 9-trickerion
# 11/250 1-root 2-TI4 4-paxren

# sep 2022
# 11/210: 1-impstr 2-nemlck 3-ankh 4-unmatched
# 10/200: 1-nemlck 2-trckrn 3-neme 4-swarmd (no ankh - no unmatched)
# 10/210: 1-ti4 2-impstrg 3-pan0 4-nemesis 9-nemlck
# 10/220: 1-swr 2-nemlck 3-pax 4-clnkleg 6-ti4 9-nem 10-unmat
# 12/200: 1-trckrn 2-impstrg 3-ankh 4-ti4 5-nemesis 6-root 7-cldspr
# 12/220: 1-kmtbs 2-ti4 3-gallerist 4-nmslck 6-cldspr 10-ankh

# oct 2022
# 11/220: 1.nemesis 2.kemet 6.TI4 9.Dimperium
# 10/200: 1.TI4 2.nemesis 3.sun
# 12/240: 1.nemesis 2.dune 3.kemet 4.TI4 5.eclipse
# 11/220: 1.TI4 2.nemesis 3.inis 4.cloud 5.dimperium 7.eclipse


# memory limits
REC_MIN_CUTOFF = 11
REC_MAX_CUTOFF = 220
# 10 220
# 10 200
# 10 240

STOCK_IN = 'In Stock'
STOCK_OUT = 'Out of Stock'

SHOP_RARU = 'Raru'
SHOP_TAKEALOT = 'Takealot'
SHOP_MEEPS_AND_VEEPS = 'Meeps and Veeps'
SHOP_TIMELESS = 'Timeless'
SHOP_GEEKHOME = 'GeekHome'
SHOP_THD = 'The Hidden Den'
SHOP_TTG = 'Tabletop Guru'
SHOP_NAMES = [SHOP_MEEPS_AND_VEEPS, SHOP_TIMELESS, SHOP_GEEKHOME, SHOP_THD, SHOP_TTG]

SOME_YEARS_AGO = now().year - 8
SIM_GROUP_SIZE = 5
IGNORE_FAMILIES = [
    'Digital Implementations',
    'Crowdfunding',
]
