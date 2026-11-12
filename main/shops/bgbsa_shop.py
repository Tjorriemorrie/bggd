import logging

from django.conf import settings

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import check_first_page, handle_item_data, missed_listings

logger = logging.getLogger(__name__)

shop_name = 'BGBSA'
shop_host = 'https://www.bgbsa.co.za'


def scrape():
    """Scrape this site."""
    shop = upsert_shop(shop_name)
    headers = {'Authorization': f'Bearer {settings.BGBSA_BEARER}'}
    url = f'{shop_host}/api/all.json'
    res = get(url, headers=headers)
    data = res.json()['listings']
    check_first_page(shop_name, url, 1, data)
    logger.info(f'🛒 Fetched feed: listings={len(data)}')

    for item in data:
        href = item['url']
        first_game = item['games'][0]
        name = first_game.get('name')
        bgg_id = first_game.get('bgg_id')
        img_src = first_game.get('image') or first_game.get('resized_image')
        if not img_src:
            logger.info(f'No image for {first_game}')
            continue
        if item['state'] == 'sold':
            in_stock = False
            price_value = None
        elif item['state'] == 'active':
            in_stock = True
            price_value = float(item['price'])
        else:
            logger.error(f'❌ Unknown listing state: state={item["state"]}, url={href}')
            raise NotImplementedError(f'Unknown state: {item["state"]}')

        params = {
            'bgg_id': bgg_id,
            'is_new': False,
        }
        handle_item_data(shop, name, href, img_src, in_stock, price_value, **params)

    shop = upsert_shop(shop_name)
    missed_listings(shop)
    logger.info(f'🛒 Scraped shop: shop={shop_name}, listings={len(data)}')
