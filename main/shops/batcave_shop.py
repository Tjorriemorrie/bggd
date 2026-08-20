import ast
import logging

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price
from main.sleeves import parse_sleeve_size

logger = logging.getLogger(__name__)

shop_name = 'Batcave'
shop_host = 'https://www.batcave.co.za'

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
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa
        # noqa E501
    }
    params = {'page': page}
    res = get(url, params=params, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    if 'there are no products in this collection' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('div', id='Collection')
    if container:
        rows = container.find_all('ul')[0].find_all('li', recursive=False)
    else:
        # the search prints its hits as a list view rather than the shelf grid
        rows = html.select('ul.list-view-items > li.list-view-item')
    if not rows:
        return False
    for row in rows:
        img_tag = row.find('img')
        if not img_tag:
            logger.info(f'{row.get_text(separator=" ", strip=True)} HAS NO IMAGE '.center(99, '!'))
            continue  # skip bad shitty products
        if img_tag.get('data-widths'):
            img_widths = ast.literal_eval(img_tag['data-widths'])
            img_src_raw = 'https:' + img_tag['data-src']
            img_src = img_src_raw.replace('{width}', str(img_widths[-1]))
        else:
            # the list view prints one already-sized image
            img_src = 'https:' + img_tag['src']
        title = row.select_one('div.h4') or row.select_one('span.product-card__title')
        name = title.get_text(separator=' ', strip=True)
        if sleeves and not parse_sleeve_size(name):
            continue
        anchor = row.find('a')
        href = shop_host + anchor['href']
        # price details
        if 'Sold out' in row.text:
            in_stock = False
            price_value = None
        else:
            in_stock = True
            price_txt = row.find('span', class_='price-item price-item--sale').get_text(strip=True)
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
    for url, sleeves in urls:
        logger.info(f' Scraping {url} '.center(99, '='))
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
