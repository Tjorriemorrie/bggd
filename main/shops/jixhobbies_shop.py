import logging

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

shop_name = 'Jix Hobbies'
shop_host = 'https://jixhobbies.co.za'


def worker(page: int) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    params = {
        'page': page,
    }
    url = f'{shop_host}/collections/board-games-card-games'
    res = get(url, params=params, headers=headers, redirect=True)
    logger.info(f'Scraped {res.request.url}...')
    if 'There are no products in this collection.' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.select_one('div.collection-grid.view-grid')
    rows = container.find_all('div', recursive=False)
    if not rows:
        return False
    for row in rows:
        img_src = 'https:' + row.find('img')['src']
        anchor = row.find('div', class_='desc').find('a')
        name = anchor.get_text(separator=' ', strip=True)
        href = shop_host + anchor['href']
        # price details
        in_stock = True
        price_txt = row.find('div', class_='price').get_text(strip=True)
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
