import logging

from bs4 import BeautifulSoup

from main.games import get
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price
from main.sleeves import parse_sleeve_size

logger = logging.getLogger(__name__)

shop_name = 'Timeless'
shop_host = 'https://www.timelessboardgames.co.za'

# The shop's own categories: 1 is the board game shelf, 120 the card sleeves.
# The site search does not filter, so the sleeve category stands in for it, and
# only sized sleeves are kept off it.
CATEGORY_BOARD_GAMES = 1
CATEGORY_SLEEVES = 120
categories = [
    (CATEGORY_BOARD_GAMES, False),
    (CATEGORY_SLEEVES, True),
]


def worker(page: int, category: int = CATEGORY_BOARD_GAMES, sleeves: bool = False) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    url = f'{shop_host}/online-shop/'
    params = {
        'page': page,
        'category': category,
    }
    res = get(url, params=params, headers=headers)
    logger.info(f'Scraped {res.request.url}...')
    if 'No games met your criteria' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    # every card on the sheet is a w3-card, chrome and brand tiles included;
    # a product is the one carrying a name and a price.
    rows = [
        row for row in html.find_all('div', class_='w3-card') if row.find('p', class_='w3-medium')
    ]
    if not rows:
        return False
    for row in rows:
        img_src = row.find_all('img', class_='w3-image')[0]['src']
        name = row.find_all('p', class_='w3-medium')[0].get_text(separator=' ', strip=True)
        if sleeves and not parse_sleeve_size(name):
            continue
        for anchor in row.find_all('a'):
            if 'boardgames/' in anchor['href']:
                href = shop_host + '/' + anchor['href']
                break
        else:
            logger.error(f'No valid href found {name}')
            continue
        is_new = 'Pre-loved' not in row.text
        # price details
        if 'Out of stock' in row.text:
            in_stock = False
            price_value = None
        else:
            in_stock = True
            price_p = row.find_all('p', class_='w3-medium')[1]
            # when discounted, a <strike> holds the old price before the current one
            old_price = price_p.find('strike')
            if old_price:
                old_price.extract()
            price_value = parse_price(price_p.get_text(strip=True))
        params = {'is_new': is_new}

        handle_item_data(shop, name, href, img_src, in_stock, price_value, **params)

    return True


def worker_wrapper(*args, **kwargs):
    """Wrap worker."""
    try:
        return worker(*args, **kwargs)
    except Exception:
        logger.exception('Error during worker')
        raise


def scrape_site():
    """Scrape pages."""
    for category, sleeves in categories:
        page = 0
        while True:
            page += 1
            outcome = worker(page, category=category, sleeves=sleeves)
            if not outcome:
                break


def scrape():
    """Scrape this site."""
    scrape_site()
    shop = upsert_shop(shop_name)
    missed_listings(shop)
