import logging

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import base_scrape, handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

shop_name = 'Timeless'
shop_host = 'https://www.timelessboardgames.co.za'


def worker(page: int) -> list:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    url = f'{shop_host}/online-shop/'
    params = {
        'page': page,
        'category': 1,
    }
    res = get(url, params=params, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    if 'No games met your criteria' in res.text:
        return []

    html = BeautifulSoup(res.text, 'html.parser')
    rows = html.find_all('div', class_='w3-card')
    for row in rows[2:-2]:
        img_src = row.find_all('img')[0]['src']
        name = row.find_all('p', class_='w3-small')[0].get_text(separator=' ', strip=True)
        href = shop_host + '/' + row.find_all('a')[0]['href']
        is_new = 'Pre-loved' not in row.text
        # price details
        if 'Out of stock' in row.text:
            in_stock = False
            price_value = None
        else:
            in_stock = True
            price_txt = row.find_all('p', class_='w3-medium')[0].find('strong').get_text(strip=True)
            price_value = parse_price(price_txt)
        params = {'is_new': is_new}

        handle_item_data(shop, name, href, img_src, in_stock, price_value, **params)

    return [page + 1, page + 2]


def worker_wrapper(*args, **kwargs):
    """Wrap worker."""
    try:
        return worker(*args, **kwargs)
    except Exception:
        logger.exception('Error during worker')
        raise


def scrape():
    """Scrape this site."""
    base_scrape(worker_wrapper)
    shop = upsert_shop(shop_name)
    missed_listings(shop)
