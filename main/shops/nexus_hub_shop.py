import logging
import re

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price
from main.sleeves import parse_sleeve_size

logger = logging.getLogger(__name__)

shop_name = 'Nexus Hub'
shop_host = 'https://nexushub.co.za'

# The board game shelf, then whatever the site search turns up for sleeves. That
# search hits everything with the word in it, so only sized sleeves are kept.
# Both are templates: this shop numbers its search pages in the path.
urls = [
    (f'{shop_host}/products/board-games-cid193.html?page={{page}}', False),
    (f'{shop_host}/profile/search/search_box/sleeves/pageProduct/{{page}}.html', True),
]


def worker(url_template: str, page: int, sleeves: bool = False) -> set[str]:
    """Scrape page, returning the urls of the products it held."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    url = url_template.format(page=page)
    res = get(url, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    last_page = 50
    if page >= last_page:
        return set()

    html = BeautifulSoup(res.text, 'html.parser')
    rows = html.find_all('div', class_='product-item')
    if not rows:
        return set()
    hrefs = set()
    for row in rows:
        anchor = row.find_all('a')[1]
        href = shop_host + anchor['href']
        try:
            img_src = shop_host + row.find('img')['src']
        except TypeError:
            continue
        name = anchor.get_text(separator=' ', strip=True)
        # Remove newlines and extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        hrefs.add(href)
        if sleeves and not parse_sleeve_size(name):
            continue
        # price details
        in_stock = True
        price_tag = row.select_one('p.price')
        price_txt = price_tag.get_text(strip=True)
        price_value = parse_price(price_txt)

        handle_item_data(shop, name, href, img_src, in_stock, price_value)

    return hrefs


def worker_wrapper(*args, **kwargs):
    """Wrapper for worker."""
    try:
        return worker(*args, **kwargs)
    except Exception:
        logger.exception('Error during worker')
        raise


def scrape_site():
    """Scrape pages."""
    for url_template, sleeves in urls:
        seen = set()
        page = 0
        while True:
            page += 1
            hrefs = worker(url_template, page, sleeves=sleeves)
            # An out-of-range search page is served as the last one again, so a
            # page that carries nothing new is the end of the results.
            if not hrefs or hrefs <= seen:
                break
            seen |= hrefs


def scrape():
    """Scrape this site."""
    scrape_site()
    shop = upsert_shop(shop_name)
    missed_listings(shop)
