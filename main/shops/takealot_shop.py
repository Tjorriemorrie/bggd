import logging
import os
import time

import requests

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

_proxy = os.environ.get('TAKEALOT_PROXY')
_request_delay = 1.0


def _get_session():
    """Create a requests session with proxy and browser-like headers."""
    session = requests.Session()
    if _proxy:
        session.proxies = {'http': _proxy, 'https': _proxy}
    session.headers.update(
        {
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            ),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'{shop_host}/',
            'Origin': shop_host,
        }
    )
    return session


def fetch_page(session, after=None):
    """Fetch a single page of results from the Takealot API."""
    url = api_base
    if after:
        url += f'&after={after}'
    time.sleep(_request_delay)
    timeout = 30
    res = session.get(url, timeout=timeout)
    ok = 200
    if res.status_code != ok:
        logger.warning(f'Got status {res.status_code}')
        return None
    return res.json()


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

        # stock & price — buybox prices indicate the item is purchasable
        buybox = views.get('buybox_summary', {})
        prices = buybox.get('prices', [])
        price_value = float(prices[0]) if prices else None
        in_stock = price_value is not None

        handle_item_data(shop, title, href, img_src, in_stock, price_value)


def scrape_site():
    """Scrape all pages via cursor-based pagination."""
    if not _proxy:
        logger.warning(
            'TAKEALOT_PROXY not set — Takealot blocks datacenter IPs. '
            'Set TAKEALOT_PROXY=socks5://user:pass@host:port'
        )
    session = _get_session()
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
        data = fetch_page(session, after)
        if not data:
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


def scrape():
    """Scrape this site."""
    scrape_site()
    shop = upsert_shop(shop_name)
    missed_listings(shop)
