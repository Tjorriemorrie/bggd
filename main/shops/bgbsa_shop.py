import logging

from django.conf import settings

from main.errors import ListingImageError
from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import missed_listings, upsert_listing, upsert_price

logger = logging.getLogger(__name__)

shop_name = 'BGBSA'
shop_host = 'https://www.bgbsa.co.za'


def scrape():
    """Scrape this site."""
    shop = upsert_shop(shop_name)
    headers = {'Authorization': f'Bearer {settings.BGBSA_BEARER}'}
    res = get(f'{shop_host}/api/all.json', headers=headers)
    data = res.json()['listings']

    for item in data:
        href = item['url']
        first_game = item['games'][0]
        name = first_game['name']
        bgg_id = first_game['bgg_id']
        img_src = first_game['image']
        if item['state'] == 'sold':
            in_stock = False
            price_value = None
        elif item['state'] == 'active':
            in_stock = True
            price_value = float(item['price'])
        else:
            raise NotImplementedError(f'Unknown state: {item["state"]}')

        try:
            params = {
                'bgg_id': bgg_id,
                'is_new': False,
            }
            listing = upsert_listing(shop, name, href, img_src, **params)
        except ListingImageError:
            continue
        price = upsert_price(listing, in_stock, price_value)
        logger.info(f'{listing} has price {price}')

    shop = upsert_shop(shop_name)
    missed_listings(shop)
