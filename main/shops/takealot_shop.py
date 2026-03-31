import json
import logging

from botasaurus.browser import Driver, browser

from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings

logger = logging.getLogger(__name__)

enabled = True
shop_name = 'Takealot'
shop_host = 'https://www.takealot.com'
api_base = (
    'https://api.takealot.com/rest/v-1-16-0/'
    'searches/products?department_slug=toys&category_slug=board-games-25346'
)
IMG_SIZE = 'fb'


@browser(headless=True, reuse_driver=True, close_on_crash=True)
def fetch_all_pages(driver: Driver, _data):
    """Fetch all pages using the browser to bypass bot detection."""
    shop = upsert_shop(shop_name)
    after = None
    max_pages = 100
    page = 0
    while True:
        page += 1
        if page > max_pages:
            logger.info(f'Reached max pages ({max_pages}), stopping.')
            break
        logger.info(f' Scraping page {page} '.center(99, '='))

        url = api_base
        if after:
            url += f'&after={after}'

        driver.get(url)
        try:
            raw = driver.page_text
            data = json.loads(raw)
        except (json.JSONDecodeError, Exception):
            logger.warning('Failed to parse JSON response')
            break

        products = data.get('sections', {}).get('products', {})
        results = products.get('results', [])
        if not results:
            logger.info('No results found, stopping.')
            break

        logger.info(f'Got {len(results)} results on page {page}')
        process_results(shop, results)

        # next page cursor
        paging = products.get('paging', {})
        after = paging.get('next_is_after')
        if not after:
            logger.info('No more pages.')
            break


def process_results(shop, results):
    """Extract item data from API results."""
    for item in results:
        views = item.get('product_views')
        if not views:
            continue
        core = views.get('core', {})
        title = core.get('title')
        slug = core.get('slug')
        product_id = core.get('id')
        if not title or not slug or not product_id:
            continue

        href = f'{shop_host}/{slug}/PLID{product_id}'

        # image
        images = views.get('gallery', {}).get('images', [])
        img_src = images[0].replace('{size}', IMG_SIZE) if images else ''
        if not img_src:
            continue

        # stock & price
        stock = views.get('stock_availability_summary', {})
        in_stock = stock.get('is_in_stock', False)
        buybox = views.get('buybox_summary', {})
        prices = buybox.get('prices', [])
        price_value = float(prices[0]) if prices else None

        handle_item_data(shop, title, href, img_src, in_stock, price_value)


def scrape():
    """Scrape this site."""
    fetch_all_pages()
    shop = upsert_shop(shop_name)
    missed_listings(shop)
