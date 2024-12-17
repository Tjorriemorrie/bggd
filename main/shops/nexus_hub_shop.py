import logging
import re

from bs4 import BeautifulSoup
from django.conf import settings

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import base_scrape, handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

shop_name = 'Nexus Hub'
shop_host = 'https://nexushub.co.za'


def worker(page: int) -> list:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    url = f'{shop_host}/products/board-games-cid193.html'
    params = {
        'page': page,
    }
    res = get(url, params=params, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    last_page = 50
    if page >= last_page:
        return []

    html = BeautifulSoup(res.text, 'html.parser')
    rows = html.find_all('div', class_='product-item')
    for row in rows:
        anchor = row.find_all('a')[1]
        href = shop_host + anchor['href']
        try:
            img_src = shop_host + row.find('img')['src']
        except TypeError:
            continue
        name = anchor.get_text(separator=' ', strip=True)
        # Remove newlines and extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        # price details
        in_stock = True
        price_tag = row.select_one('p.price')
        price_txt = price_tag.get_text(strip=True)
        price_value = parse_price(price_txt)

        handle_item_data(shop, name, href, img_src, in_stock, price_value)

    if len(rows) > 0:
        return [page + i for i in range(1, settings.PROCESS_POOL + 1)]
    return []


def worker_wrapper(page):
    """Wrapper for worker."""
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
