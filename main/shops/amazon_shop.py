import logging
import re
import time

from botasaurus_requests import request as bot_request
from bs4 import BeautifulSoup

from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price

logger = logging.getLogger(__name__)

enabled = True
shop_name = 'Amazon'
shop_host = 'https://www.amazon.co.za'
# https://www.amazon.co.za/s?i=toys&rh=n:28002628031,p_72:28056829031,p_6:A34KVLZUJN6MA,p_n_availability:28056815031&dc=&page=1


def _request_with_backoff(url, max_retries=5, base_delay=3):
    """GET with exponential backoff on 503 responses."""
    service_unavailable = 503
    for attempt in range(max_retries):
        res = bot_request.get(url, headers={})
        logger.info(f'Scraped {url} (status {res.status_code})...')
        if res.status_code != service_unavailable:
            return res
        delay = base_delay * (2**attempt)
        logger.warning(f'Got 503, retrying in {delay}s (attempt {attempt + 1}/{max_retries})')
        time.sleep(delay)
    return res


def worker(page: int) -> bool:
    """Scrape page."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    url = f'{shop_host}/s'
    params = {
        'i': 'toys',
        'rh': 'n:28002628031,p_72:28056829031,p_6:A34KVLZUJN6MA,p_n_availability:28056815031',
        'dc': '',
        'page': str(page),
    }
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    full_url = f'{url}?{query}'

    res = _request_with_backoff(full_url)
    ok = 200
    if res.status_code != ok:
        logger.warning(f'Got status {res.status_code}')
        return False
    if 'Try checking your spelling or use more general terms' in res.text:
        return False

    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('div', class_='s-result-list')
    if not container:
        logger.warning('No result list container found')
        return False
    rows = container.find_all('div', class_='s-result-item')
    if not rows:
        return False
    for row in rows:
        min_txt_len = 100
        if len(row.text) < min_txt_len:
            continue
        img_tag = row.find('img', class_='s-image')
        link_tag = row.find('a', class_='a-link-normal')
        h2_tag = row.find('h2')
        if not img_tag or not link_tag or not h2_tag:
            continue
        img_src = img_tag['src']
        href = shop_host + link_tag['href']
        href = re.sub(r'/ref.*$', '', href)
        name = h2_tag.get_text(separator=' ', strip=True)
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
    max_pages = 50
    page = 0
    while True:
        page += 1
        if page > max_pages:
            logger.info(f'Reached max pages ({max_pages}), stopping.')
            break
        outcome = worker(page)
        if not outcome:
            break


def scrape():
    """Scrape this site."""
    scrape_site()
    shop = upsert_shop(shop_name)
    missed_listings(shop)
