import logging
import re

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

shop_name = 'Amazon'
shop_host = 'https://www.amazon.co.za'


def worker(page: int) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
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
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('div', class_='s-result-list')
    rows = container.find_all('div', class_='s-result-item')
    if not rows:
        return False
    for row in rows:
        min_txt_len = 100
        if len(row.text) < min_txt_len:
            continue
        img_src = row.find('img', class_='s-image')['src']
        href = shop_host + row.find('a', class_='a-link-normal')['href']
        href = re.sub(r'/ref.*$', '', href)
        name = row.find('h2').get_text(separator=' ', strip=True)
        # price details
        in_stock = True
        try:
            price_txt = (
                row.select_one('span.a-price').select_one('span.a-offscreen').get_text(strip=True)
            )
            price_value = parse_price(price_txt)
            price_value /= 100
        except AttributeError:
            if 'Currently unavailable.' in row.text:
                in_stock = False
                price_value = None
            else:
                raise
        handle_item_data(shop, name, href, img_src, in_stock, price_value)

    return True


def worker_wrapper(page):
    """Worker wrapper."""
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
