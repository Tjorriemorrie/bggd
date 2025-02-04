import logging
import re

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

shop_name = 'Maximus Games'
shop_host = 'https://maximusgames.co.za'


def worker(page: int) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    url = f'{shop_host}/collections/all'
    params = {
        'page': page,
    }
    res = get(url, params=params, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    if 'No products found' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('ul', id='product-grid')
    rows = container.find_all('li', recursive=False)
    if not rows:
        return False
    for row in rows:
        anchor = row.find_all('a')[-1]
        href = shop_host + anchor['href']
        try:
            img_src = 'https:' + row.find('img')['srcset']
        except TypeError:
            continue
        name = anchor.get_text(separator=' ', strip=True)
        # Remove newlines and extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        if 'Preorder' in name:
            continue
        # price details
        sold_out_wrapper = row.find('div', class_='card__badge bottom left')
        sold_out_tag = sold_out_wrapper.find('span', text='Sold out') if sold_out_wrapper else False
        if sold_out_tag:
            in_stock = False
            price_value = None
        else:
            in_stock = True
            price_tag = row.select_one('span.price-item--last')
            if not price_tag:
                price_tag = row.select_one('span.price-item--regular')
            price_txt = price_tag.get_text(strip=True)
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
