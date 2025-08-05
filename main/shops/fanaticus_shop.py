import logging
import re

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

shop_name = 'Fanaticus'
shop_host = 'https://fanaticus.co.za'


def worker(page: int) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    url = f'{shop_host}/product-category/board-games/page/{page}/'
    params = {}
    redirect = page == 1
    res = get(url, params=params, headers=headers, redirect=redirect)
    logger.info(f'Scraped {res.request.url}...')
    if 'It is pitch black. You are likely to be eaten by a grue.' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('ul', class_=lambda x: x and 'potter-grid' in x.split())
    rows = container.find_all(
        'li', class_=lambda x: x and 'type-product' in x.split(), recursive=False
    )
    if not rows:
        return False
    for row in rows:
        anchor = row.find_all('a')[0]
        href = anchor['href']
        img_tag = row.find('img')
        img_src = img_tag.get('data-src') or img_tag.get('data-lazy-src') or img_tag.get('src')
        name = row.find('h3', class_='woocommerce-loop-product__title').get_text(strip=True)
        # Remove newlines and extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        if name == 'Sample Product':
            continue
        # price details
        in_stock = True
        price_tag = row.find_all('span', class_='woocommerce-Price-amount amount')[-1]
        price_txt = price_tag.get_text(strip=True).replace(' ', '')
        price_value = parse_price(price_txt)

        handle_item_data(shop, name, href, img_src, in_stock, price_value)

    return True


def worker_wrapper(page):
    """Wrapper for worker."""
    try:
        return worker(page)
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
