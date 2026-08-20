import logging

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price
from main.sleeves import parse_sleeve_size

logger = logging.getLogger(__name__)

shop_name = 'The Geek Home'
shop_host = 'https://www.geekhome.co.za'

# The board game shelf, then whatever the site search turns up for sleeves. That
# search hits everything with the word in it, so only sized sleeves are kept.
# Both are templates: WordPress numbers its pages in the path.
urls = [
    (f'{shop_host}/product-category/boardgames/page/{{page}}/', False),
    (f'{shop_host}/page/{{page}}/?s=sleeves&post_type=product', True),
]


def worker(url_template: str, page: int, sleeves: bool = False) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    url = url_template.format(page=page)
    res = get(url, headers=headers, redirect=True)
    logger.info(f'Scraped {res.request.url}...')
    if 'It looks like nothing was found at this location' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    # the search sheet lays its hits out in a different column count
    container = html.find('ul', class_=lambda x: x and 'products' in x.split())
    rows = container.find_all('li', recursive=False) if container else []
    if not rows:
        return False
    for row in rows:
        img_src = row.find('img')['src']
        name = row.find('h2').get_text(separator=' ', strip=True)
        if sleeves and not parse_sleeve_size(name):
            continue
        href = row.find('a')['href']
        # price details
        sold_out_span = row.find('span', class_='now_sold')
        if sold_out_span and 'SOLD OUT' in sold_out_span.text.strip():
            in_stock = False
            price_value = None
        else:
            in_stock = True
            price_txt = row.find_all('bdi')[-1].get_text(strip=True)
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
    for url_template, sleeves in urls:
        page = 0
        while True:
            page += 1
            outcome = worker(url_template, page, sleeves=sleeves)
            if not outcome:
                break


def scrape():
    """Scrape this site."""
    scrape_site()
    shop = upsert_shop(shop_name)
    missed_listings(shop)
