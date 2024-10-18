import logging
import re

from bs4 import BeautifulSoup
from django.conf import settings

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import base_scrape, handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

shop_name = 'Amazon'
shop_host = 'https://www.amazon.co.za'


def worker(page: int) -> list:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',
        # noqa E501
    }
    url = f'{shop_host}/s'
    params = {
        'i': 'toys',
        'rh': 'n:28002628031,p_72:28056829031,p_6:A34KVLZUJN6MA,p_n_availability:28056815031',
        'dc': '',
        # 'ds': 'v1:YzAW0qEQtL1K5oouJPBjxnT3d2hYH3OjHPuLt6K5EZ0',
        'page': page,
        # 'content-id': 'amzn1.sym.7738ade6-b071-4ce1-991e-a3a167042a7a',
    }
    res = get(url, params=params, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    if 'Try checking your spelling or use more general terms' in res.text:
        return []

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('div', class_='s-result-list')
    rows = container.find_all('div', class_='s-result-item')
    for row in rows:
        if len(row.text) < 100:
            continue
        img_src = row.find('img', class_='s-image')['src']
        href = shop_host + row.find('a', class_='a-link-normal')['href']
        href = re.sub(r'/ref.*$', '', href)
        name = row.find('h2').get_text(separator=' ', strip=True)
        # price details
        in_stock = True
        price_txt = (
            row.select_one('span.a-price').select_one('span.a-offscreen').get_text(strip=True)
        )
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
