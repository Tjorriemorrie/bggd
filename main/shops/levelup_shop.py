import logging

from bs4 import BeautifulSoup
from django.conf import settings

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import base_scrape, handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

shop_name = 'Level Up'
shop_host = 'https://levelupstore.co.za'


def worker(page: int) -> list:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',
        # noqa E501
    }
    url = f'{shop_host}/collections/all-board-games'
    params = {
        'page': page,
    }
    res = get(url, params=params, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    if 'No products found in this collection' in res.text:
        return []

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('div', class_='container collection-matrix')
    rows = container.find_all('div', recursive=False)
    for row in rows:
        anchor = row.find_all('a')[-1]
        img_src = 'https:' + row.find('img')['data-src']
        href = shop_host + anchor['href']
        name = anchor.get_text(separator=' ', strip=True)
        # price details
        sold_out_span = row.find('span', class_='product-thumbnail__price')
        if 'Sold Out' in sold_out_span.text.strip():
            in_stock = False
            price_value = None
        else:
            in_stock = True
            price_txt = row.select_one('span.money').get_text(strip=True)
            price_value = parse_price(price_txt)

        handle_item_data(shop, name, href, img_src, in_stock, price_value)

    if len(rows) > 0:
        return [page + i for i in range(1, settings.PROCESS_POOL + 1)]
    return []


def worker_wrapper(page):
    try:
        return worker(page)
    except Exception:
        logger.exception('Error during worker')
        raise


def scrape():
    """Scrape this site."""
    base_scrape(worker_wrapper)
    shop = upsert_shop(shop_name)
    missed_listings(shop)
