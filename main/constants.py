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
REC_MIN_CUTOFF = 20
REC_MAX_CUTOFF = 100


STOCK_IN = 'In Stock'
STOCK_OUT = 'Out of Stock'

SHOP_MEEPS_AND_VEEPS = 'Meeps and Veeps'
SHOP_TIMELESS = 'Timeless'
SHOP_GEEKHOME = 'GeekHome'
SHOP_THD = 'The Hidden Den'
SHOP_TTG = 'Tabletop Guru'
SHOP_GARGOYLE = 'Grinning Gargoyle'
SHOP_SWORD_AND_BOARD = 'Sword and Board'
SHOP_LEVEL_UP = 'Level Up'
SHOP_AMAZON = 'Amazon'
SHOP_NAMES = [
    SHOP_TIMELESS,
    SHOP_MEEPS_AND_VEEPS,
    SHOP_LEVEL_UP,
    SHOP_GEEKHOME,
    SHOP_GARGOYLE,
    SHOP_TTG,
    SHOP_THD,
    SHOP_AMAZON,
    SHOP_SWORD_AND_BOARD,
]

REGEX_BOARD_GAME = r'(?:The\s*)?Board\s*Game'
REGEX_BRACKETS = r'\s*\([^)]*\)$'

REVIEW_STATUS_OWN = 'own'
REVIEW_STATUS_PREV_OWNED = 'prevowned'
REVIEW_STATUS_WISH_LIST = 'wishlist'
REVIEW_STATUS_NONE = 'none'
REVIEW_STATUS_CHOICES = [
    [REVIEW_STATUS_OWN, REVIEW_STATUS_OWN],
    [REVIEW_STATUS_PREV_OWNED, REVIEW_STATUS_PREV_OWNED],
    [REVIEW_STATUS_WISH_LIST, REVIEW_STATUS_WISH_LIST],
    [REVIEW_STATUS_NONE, REVIEW_STATUS_NONE],
]

SOME_YEARS_AGO = now().year - 8
SIM_GROUP_SIZE = 5
IGNORE_FAMILIES = [
    'Digital Implementations',
    'Crowdfunding',
]

COUNTRY_SOUTH_AFRICA = 'South Africa'

PROVINCE_GAUTENG = 'Gauteng'
PROVINCE_WESTERN_CAPE = 'Western Cape'
PROVINCE_FREE_STATE = 'Free State'
PROVINCE_MPUMALANGA = 'Mpumalanga'
PROVINCE_KWAZULU_NATAL = 'Kwazulu-Natal'
PROVINCE_NORTH_WEST = 'North West'
PROVINCE_EASTERN_CAPE = 'Eastern Cape'
PROVINCE_LIMPOPO = 'Limpopo'
PROVINCE_NORTHERN_CAPE = 'Northern Cape'
PROVINCES_LIST = [
    PROVINCE_WESTERN_CAPE,
    PROVINCE_NORTHERN_CAPE,
    PROVINCE_EASTERN_CAPE,
    PROVINCE_GAUTENG,
    PROVINCE_MPUMALANGA,
    PROVINCE_LIMPOPO,
    PROVINCE_NORTH_WEST,
    PROVINCE_FREE_STATE,
    PROVINCE_KWAZULU_NATAL,
]

CITY_BENONI = 'Benoni'
CITY_BLOEMFONTEIN = 'Bloemfontein'
CITY_BOKSBURG = 'Boksburg'
CITY_CAPE_TOWN = 'Cape Town'
CITY_CENTURION = 'Centurion'
CITY_CHATSWORTH = 'Chatsworth'
CITY_CLARENS = 'Clarens'
CITY_DURBAN = 'Durban'
CITY_EAST_LONDON = 'East London'
CITY_ELLISRAS = 'Ellisras'
CITY_ELYSIUM = 'Elysium'
CITY_GEORGE = 'George'
CITY_GORDONS_BAY = "Gordon'S Bay"
CITY_GRAHAMSTOWN = 'Grahamstown'
CITY_HARTBEESPOORT = 'Hartbeespoort'
CITY_HOEDSPRUIT = 'Hoedspruit'
CITY_HOUT_BAY = 'Hout Bay'
CITY_JAN_KEMPDORP = 'Jan Kempdorp'
CITY_JOHANNESBURG = 'Johannesburg'
CITY_KRUGERSDORP = 'Krugersdorp'
CITY_LADY_GREY = 'Lady Grey'
CITY_MBOMBELA = 'Mbombela'
CITY_MIDDELBURG = 'Middelburg'
CITY_MIDRAND = 'Midrand'
CITY_MOSSEL_BAY = 'Mossel Bay'
CITY_MTUNZINI = 'Mtunzini'
CITY_NELSPRUIT = 'Nelspruit'
CITY_ORKNEY = 'Orkney'
CITY_PIET_RETIEF = 'Piet Retief'
CITY_PIETERMARITZBURG = 'Pietermaritzburg'
CITY_PIETERSBURG = 'Pietersburg'
CITY_PORT_ELIZABETH = 'Port Elizabeth'
CITY_PORT_SHEPSTONE = 'Port Shepstone'
CITY_POTCHEFSTROOM = 'Potchefstroom'
CITY_QUEENSBURGH = 'Queensburgh'
CITY_PRETORIA = 'Pretoria'
CITY_RANDBURG = 'Randburg'
CITY_RICHARDS_BAY = 'Richards Bay'
CITY_ROODEPOORT = 'Roodepoort'
CITY_SAINT_HELENA_BAY = 'Saint Helena Bay'
CITY_SASOLBURG = 'Sasolburg'
CITY_SCOTTBURGH = 'Scottburgh'
CITY_SECUNDA = 'Secunda'
CITY_SEDGEFIELD = 'Sedgefield'
CITY_SPRINGS = 'Springs'
CITY_SOMERSET_WEST = 'Somerset West'
CITY_STELLENBOSCH = 'Stellenbosch'
CITY_WELKOM = 'Welkom'
CITY_WOODSTOCK = 'Woodstock'
CITY_VEREENIGING = 'Vereeniging'
CITIES = {
    PROVINCE_GAUTENG: [
        CITY_BENONI,
        CITY_BOKSBURG,
        CITY_CENTURION,
        CITY_JOHANNESBURG,
        CITY_KRUGERSDORP,
        CITY_MIDRAND,
        CITY_PRETORIA,
        CITY_RANDBURG,
        CITY_ROODEPOORT,
        CITY_SPRINGS,
        CITY_VEREENIGING,
    ],
    PROVINCE_WESTERN_CAPE: [
        CITY_CAPE_TOWN,
        CITY_GEORGE,
        CITY_GORDONS_BAY,
        CITY_HOUT_BAY,
        CITY_MOSSEL_BAY,
        CITY_SAINT_HELENA_BAY,
        CITY_SEDGEFIELD,
        CITY_SOMERSET_WEST,
        CITY_STELLENBOSCH,
    ],
    PROVINCE_FREE_STATE: [
        CITY_BLOEMFONTEIN,
        CITY_CLARENS,
        CITY_SASOLBURG,
        CITY_WELKOM,
    ],
    PROVINCE_MPUMALANGA: [
        CITY_MBOMBELA,
        CITY_MIDDELBURG,
        CITY_NELSPRUIT,
        CITY_PIET_RETIEF,
        CITY_SECUNDA,
    ],
    PROVINCE_KWAZULU_NATAL: [
        CITY_CHATSWORTH,
        CITY_DURBAN,
        CITY_ELYSIUM,
        CITY_MTUNZINI,
        CITY_PIETERMARITZBURG,
        CITY_PORT_SHEPSTONE,
        CITY_QUEENSBURGH,
        CITY_RICHARDS_BAY,
        CITY_SCOTTBURGH,
    ],
    PROVINCE_NORTH_WEST: [
        CITY_HARTBEESPOORT,
        CITY_ORKNEY,
        CITY_POTCHEFSTROOM,
    ],
    PROVINCE_EASTERN_CAPE: [
        CITY_EAST_LONDON,
        CITY_GRAHAMSTOWN,
        CITY_LADY_GREY,
        CITY_PORT_ELIZABETH,
        CITY_WOODSTOCK,
    ],
    PROVINCE_LIMPOPO: [
        CITY_ELLISRAS,
        CITY_HOEDSPRUIT,
        CITY_PIETERSBURG,
    ],
    PROVINCE_NORTHERN_CAPE: [
        CITY_JAN_KEMPDORP,
    ],
}


ROWS_TABLE_HEADERS = 2
SCRAPE_REVIEWS_EXISTING_BUFFER = 100
GAME_LIMIT = 1_500
SPLIT_SIZE = 2
MINIMUM_GAME_PRICE = 100

FORMAT_PRICE_HUNDREDS = 100
FORMAT_PRICE_THOUSANDS = 1_000
