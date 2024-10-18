import logging

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import base_scrape, handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

shop_name = 'Grinning Gargoyle'
shop_host = 'https://grinning-gargoyle.co.za'


def worker(page: int) -> list:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',
        # noqa E501
    }
    url = f'{shop_host}/product-category/board/page/{page}/'
    res = get(url, headers=headers, redirect=True)
    logger.info(f'Scraped {res.request.url}...')
    if 'find a page at this URL' in res.text:
        return []

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('ul', class_='products columns-4')
    rows = container.find_all('li', recursive=False)
    for row in rows:
        img_src = row.find('img')['src']
        name_txt = row.find('h2').get_text(separator=' ', strip=True)
        if '(Pre-Order' in name_txt:
            pre_order = True
            # Split the string and keep the left part
            name = name_txt.split('(Pre-Order')[0].strip()
        else:
            pre_order = False
            name = name_txt.strip()
        href = row.find('a')['href']

        # price details
        in_stock = True
        price_txt = row.find('span', class_='price').select_one('span.amount').get_text(strip=True)
        price_value = parse_price(price_txt)
        if pre_order:
            price_value /= 0.5

        handle_item_data(
            shop, name, href, img_src, in_stock, price_value, **{'is_preorder': pre_order}
        )

    if len(rows) > 0:
        return [page + 1, page + 2]
    return []


def worker_wrapper(*args, **kwargs):
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
