import logging

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import base_scrape, handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

shop_name = 'The Hidden Den'
shop_host = 'https://thehiddenden.co.za'


def worker(page: int) -> list:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    params = {
        'swoof': '1',
        'stock': 'instock',
        'really_curr_tax': '16-product_cat',
    }
    url = f'{shop_host}/product-category/board-games/page/{page}/'
    res = get(url, headers=headers, params=params, redirect=True)
    logger.info(f'Scraped {res.request.url}...')
    if 'It looks like nothing was found at this location' in res.text:
        return []

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.select_one('div.products')
    rows = container.find_all('div', recursive=False)
    for row in rows:
        anchor = row.find('a')
        href = row.find('a')['href']
        img = anchor.find('img')
        try:
            img_src = img['data-src']
        except KeyError:
            logger.warning(f'Image data not found in data-src: {anchor.find("img")}')
            img_src = img['src']
        name = row.select_one('p.name.product-title').get_text(separator=' ', strip=True)

        # price details
        in_stock = True
        try:
            price_txt = row.find_all('bdi')[-1].get_text(strip=True)
        except IndexError:
            continue  # even 'in stock' option has dups without a price
        price_value = parse_price(price_txt)

        handle_item_data(shop, name, href, img_src, in_stock, price_value)

    if len(rows) > 0:
        return [page + 1, page + 2]
    return []


def worker_wrapper(*args, **kwargs):
    """Worker wrapper."""
    try:
        return worker(*args, **kwargs)
    except Exception:
        logger.exception('Error during worker')
        raise


def scrape():
    """Scrape this site."""
    base_scrape(worker)
    shop = upsert_shop(shop_name)
    missed_listings(shop)
