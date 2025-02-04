import logging
import re

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

enabled = 0
shop_name = 'Grinning Gargoyle'
shop_host = 'https://grinning-gargoyle.co.za'


def worker(page: int) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    url = f'{shop_host}/product-category/board/page/{page}/'
    res = get(url, headers=headers, redirect=True)
    logger.info(f'Scraped {res.request.url}...')
    if 'find a page at this URL' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('ul', class_='products columns-4')
    rows = container.find_all('li', recursive=False)
    if not rows:
        return False
    for row in rows:
        row_text = re.sub(r'\n+', ' ', row.text.casefold()).strip()
        if 'pre-order' in row_text:
            logger.info(f'Skipping pre-order: {row_text}')
            continue
        img_src = row.find('img')['src']
        name_txt = row.find('h2').get_text(separator=' ', strip=True)
        name = name_txt.strip()
        href = row.find('a')['href']

        # price details
        in_stock = True
        price_txt = row.find('span', class_='price').select_one('span.amount').get_text(strip=True)
        price_value = parse_price(price_txt)

        handle_item_data(shop, name, href, img_src, in_stock, price_value)

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
    scrape_site()
    shop = upsert_shop(shop_name)
    missed_listings(shop)
