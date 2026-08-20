import logging

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price
from main.sleeves import parse_sleeve_size

logger = logging.getLogger(__name__)

shop_name = 'Jix Hobbies'
shop_host = 'https://jixhobbies.co.za'

# The board game shelf, then whatever the site search turns up for sleeves. That
# search hits everything with the word in it, so only sized sleeves are kept.
urls = [
    (f'{shop_host}/collections/board-games-card-games', False),
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
    res = get(url, params=params, headers=headers, redirect=True)
    logger.info(f'Scraped {res.request.url}...')
    if 'There are no products in this collection.' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    # the search prints its hits into its own wrapper, same card markup
    container = html.select_one('div.collection-grid.view-grid') or html.select_one(
        'div.search-infinite-wrapper'
    )
    rows = container.find_all('div', recursive=False) if container else []
    if not rows:
        return False
    for row in rows:
        # the search cards carry a <noscript> copy first, which has no src
        img_tag = row.find('img', src=True)
        if not img_tag:
            logger.info(f'{row.get_text(separator=" ", strip=True)} HAS NO IMAGE '.center(99, '!'))
            continue
        img_src = 'https:' + img_tag['src']
        anchor = row.find('div', class_='desc').find('a')
        name = anchor.get_text(separator=' ', strip=True)
        if sleeves and not parse_sleeve_size(name):
            continue
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
