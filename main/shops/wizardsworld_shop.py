import logging

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

enabled = 0
shop_name = 'Wizards World'
shop_host = 'https://wizardsworld.co.za'


def worker(page: int) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa
        # noqa E501
    }
    url = f'{shop_host}/product-category/board-games/page/{page}/'
    res = get(url, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    if 'No Results Found' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.select_one('ul.products')
    rows = container.find_all('li', recursive=False)
    if not rows:
        return False
    for row in rows:
        img_src = row.find('img')['src']
        name = row.select_one('h2').get_text(separator=' ', strip=True)
        anchor = row.find('a')
        href = anchor['href']
        # price details
        in_stock = True
        price_txt = row.select_one('span.price').find_all('bdi')[-1].get_text(strip=True)
        price_value = parse_price(price_txt)

        handle_item_data(shop, name, href, img_src, in_stock, price_value)

    return True


def worker_wrapper(*args, **kwargs):
    """Wrap worker to catch error."""
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
