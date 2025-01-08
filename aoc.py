from itertools import permutations

NODE_MIRALETH = 'Miraleth'
NODE_WINSTEAD = 'Winstead'
NODE_HALCYON = 'Halcyon'
NODE_JOEVA = 'Joeva'
NODE_NEW_AELA = 'New Aela'

ALL_NODES = [
    NODE_MIRALETH,
    NODE_WINSTEAD,
    NODE_HALCYON,
    NODE_JOEVA,
    NODE_NEW_AELA,
]

routes = list(permutations(ALL_NODES, 2))

MIRALETH_COMMON = {
    'name': 'Case of Dunir Tools',
    'glowing': 0,
    'dim': 3,
    'dull': 6,
}
MIRALETH_UNCOMMON = {
    'name': 'Packs of Fresh Produce',
    'glowing': 0,
    'dim': 1,
    'dull': 9,
}
MIRALETH_RARE = {
    'name': 'Ancient Aelan Wine Flagons',
    'glowing': 2,
    'dim': 9,
    'dull': 3,
}
MIRALETH_HEROIC = {
    'name': 'Metal Ingots Shipment',
    'glowing': 8,
    'dim': 7,
    'dull': 9,
}
MIRALETH_EPIC = {
    'name': 'Crate of Salted Fish Cakes',
    'glowing': 5,
    'dim': 9,
    'dull': 9,
}
MIRALETH_CARGO = [
    MIRALETH_COMMON,
    MIRALETH_UNCOMMON,
    MIRALETH_RARE,
    MIRALETH_HEROIC,
    MIRALETH_EPIC,
]

JOEVA_COMMON = {
    'name': 'Daffodil Blooms',
    'glowing': 0,
    'dim': 4,
    'dull': 0,
}
JOEVA_UNCOMMON = {
    'name': 'Create of Floral Essences',
    'glowing': 1,
    'dim': 1,
    'dull': 9,
}
JOEVA_RARE = {
    'name': 'Candied Floral Petals',
    'glowing': 3,
    'dim': 1,
    'dull': 9,
}
JOEVA_HEROIC = {
    'name': 'Cask of River Roe',
    'glowing': 5,
    'dim': 4,
    'dull': 9,
}
JOEVA_EPIC = {
    'name': 'Crate of Ancien Slates',
    'glowing': 9,
    'dim': 5,
    'dull': 9,
}
JOEVA_CARGO = [
    JOEVA_COMMON,
    JOEVA_UNCOMMON,
    JOEVA_RARE,
    JOEVA_HEROIC,
    JOEVA_EPIC,
]

NEW_ALEA_COMMON = {
    'name': 'Crate of Flower Bulbs',
    'glowing': 0,
    'dim': 3,
    'dull': 8,
}
NEW_ALEA_UNCOMMON = {
    'name': 'Base of Processed Flower Petals',
    'glowing': 1,
    'dim': 1,
    'dull': 4,
}
NEW_ALEA_RARE = {
    'name': 'Case of Dandelion Wine',
    'glowing': 3,
    'dim': 0,
    'dull': 6,
}
NEW_ALEA_HEROIC = {
    'name': 'Crate of River Shells',
    'glowing': 5,
    'dim': 7,
    'dull': 4,
}
NEW_ALEA_EPIC = {
    'name': 'Dunir Puzzle Stones',
    'glowing': 9,
    'dim': 1,
    'dull': 9,
}
NEW_ALEA_CARGO = [
    NEW_ALEA_COMMON,
    NEW_ALEA_UNCOMMON,
    NEW_ALEA_RARE,
    NEW_ALEA_HEROIC,
    NEW_ALEA_EPIC,
]

VENDOR_GLOWING = 1000
VENDOR_DIM = 100
VENDOR_DULL = 10

for c in MIRALETH_CARGO:
    c['vendor'] = c['glowing'] * VENDOR_GLOWING + c['dim'] * VENDOR_DIM + c['dull'] * VENDOR_DULL

data = {r: {'priority': 1, 'runs': []} for r in routes}

FEE_CARAVAN = 1000
FEE_LAUNCH = 1000

a = 1
