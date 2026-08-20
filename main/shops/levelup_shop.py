import logging
import re

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price
from main.sleeves import parse_sleeve_size

logger = logging.getLogger(__name__)

shop_name = 'Level Up'
shop_host = 'https://levelupstore.co.za'

# The board game shelf, then whatever the site search turns up for sleeves. That
# search hits everything with the word in it, so only sized sleeves are kept.
urls = [
    (f'{shop_host}/collections/all-board-games', False),
    (f'{shop_host}/search?q=sleeves', True),
]


def worker(url: str, page: int, sleeves: bool = False) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    params = {
        'page': page,
    }
    res = get(url, params=params, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    if 'No products found in this collection' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    # the shelf and the search results print the same thumbnail card
    rows = html.select('div.product__grid-item')
    if not rows:
        return False
    for row in rows:
        if 'Pre-Order' in row.text:
            continue
        anchor = row.find_all('a')[-1]
        img_src = 'https:' + row.find('img')['data-src']
        href = shop_host + anchor['href']
        name = anchor.get_text(separator=' ', strip=True)
        # Remove newlines and extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        if sleeves and not parse_sleeve_size(name):
            continue
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

    return True


def worker_wrapper(*args, **kwargs):
    """Wrapper for worker."""
    try:
        return worker(*args, **kwargs)
    except Exception:
        logger.exception('Error during worker')
        raise


def scrape_site():
    """Scrape pages."""
    for url, sleeves in urls:
        page = 0
        while True:
            page += 1
            outcome = worker(url, page, sleeves=sleeves)
            if not outcome:
                break


def scrape():
    """Scrape this site."""
    scrape_site()
    shop = upsert_shop(shop_name)
    missed_listings(shop)
