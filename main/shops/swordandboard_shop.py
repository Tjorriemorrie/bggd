import logging
import re

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price
from main.sleeves import parse_sleeve_size

logger = logging.getLogger(__name__)

shop_name = 'Sword and Board'
shop_host = 'https://swordandboard.co.za'

# The board game shelf, then whatever the site search turns up for sleeves. That
# search hits everything with the word in it, so only sized sleeves are kept.
urls = [
    (f'{shop_host}/collections/board-games', False),
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
    res = get(url, headers=headers, params=params)
    logger.info(f'Scraped {res.request.url}...')
    if 'No Products Found' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    # the search prints its hits as a list view rather than the shelf grid
    rows = html.select(
        'ul#main-collection-product-grid > li, '
        'div.list-view-items.products-display > div.product-card-list2'
    )
    if not rows:
        return False
    for row in rows:
        row_text = re.sub(r'\n+', ' ', row.text.casefold())
        if 'pre-order' in row_text:
            logger.info(f'Skipping pre-order: {row_text}')
            continue

        anchor = row.find('a')
        href = shop_host + anchor['href']
        img_src = 'http:' + anchor.find('img')['src']
        name = row.find('div', class_='product-detail').get_text(separator=' ', strip=True)
        if 'Preorder' in name or 'preorder' in href:
            continue
        if sleeves and not parse_sleeve_size(name):
            continue
        # price details
        sold_out_tag = row.find('option')
        if sold_out_tag and 'Sold Out' in sold_out_tag.text:
            in_stock = False
            price_value = None
        else:
            in_stock = True
            price_txt = row.find('div', class_='product-price').get_text(strip=True)
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
