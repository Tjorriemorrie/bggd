import ast
import logging
import re

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import (
    handle_item_data,
    missed_listings,
    parse_price,
)

logger = logging.getLogger(__name__)

enabled = True
shop_name = 'Meeps and Veeps'
shop_host = 'https://meepsandveeps.co.za'


def worker(page: int) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    url = f'{shop_host}/collections/best-selling'
    params = {
        'page': page,
    }
    res = get(url, params=params, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    if 'there are no products matching your search' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    containers = html.find_all('div', class_='grid-uniform')
    rows = containers[1].find_all('div', recursive=False)
    if not rows:
        return False
    for row in rows:
        row_text = re.sub(r'\n+', ' ', row.text.casefold())
        if 'pre-order by' in row_text:
            logger.info(f'Skipping pre-order: {row_text}')
            continue
        img_tag = row.find('img')
        if not img_tag:
            logger.info(f'{row.get_text(separator=" ", strip=True)} HAS NO IMAGE '.center(99, '!'))
            continue  # skip bad shitty products
        img_widths = ast.literal_eval(img_tag['data-widths'])
        img_src_raw = 'https:' + img_tag['data-src']
        img_src = img_src_raw.replace('{width}', str(img_widths[-1]))
        name = row.find('p').get_text(separator=' ', strip=True)
        is_new = 'Pre-owned' not in name
        anchor = row.find('a')
        href = shop_host + anchor['href']
        # price details
        if 'Sold Out' in row.text:
            in_stock = False
            price_value = None
        else:
            in_stock = True
            price_txt = row.find_all('span')[-1].get_text(strip=True)
            price_value = parse_price(price_txt)

        handle_item_data(shop, name, href, img_src, in_stock, price_value, **{'is_new': is_new})

    return True


def worker_wrapper(*args, **kwargs):
    """Worker wrapper."""
    try:
        return worker(*args, **kwargs)
    except Exception:
        logger.exception('Error during worker')
        raise


def scrape_site():
    """Scrape pages."""
    page = 0
    while True:
        page += 1
        outcome = worker(page)
        if not outcome:
            break


def scrape():
    """Scrape this site."""
    # scrape_site()
    shop = upsert_shop(shop_name)
    missed_listings(shop)
