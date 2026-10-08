import logging
import re

from bs4 import BeautifulSoup

from main.constants import CATEGORY_CARD_GAME, CATEGORY_RPG
from main.games import get
from main.models import Listing, Shop
from main.selectors import upsert_shop
from main.shops.helpers import handle_item_data, missed_listings, parse_price
from main.sleeves import SLEEVE_SIZE_RE, parse_sleeve_size

logger = logging.getLogger(__name__)

enabled = 0
shop_name = 'Pwned Games'
shop_host = 'https://www.pwnedgames.co.za'

# The board, card and tabletop (RPG) shelves, then the whole trading card games
# section. VirtueMart pages by item offset, so a big page keeps the requests few.
# A shelf's category is only given to listings it first creates; None leaves it unset.
# Last comes whatever the site search turns up for sleeves; only sized sleeves are kept.
# Sleeves are left to that search alone: a shelf would store them without their size.
PAGE_SIZE = 200
urls = [
    (f'{shop_host}/board-card-games/board-games', None, False),
    (f'{shop_host}/board-card-games/card-games', None, False),
    (f'{shop_host}/board-card-games/other-tabletop-games', CATEGORY_RPG, False),
    (f'{shop_host}/trading-card-games-tcg', CATEGORY_CARD_GAME, False),
    (f'{shop_host}/vm-search/search?keyword=sleeves', None, True),
]
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
}

# Sleeve sizes in inches, as `2.5" x 3.5"` or `2-1/2" x 3-1/2"`; a side is a decimal,
# a whole number with a fraction, or a bare fraction.
INCH_SIDE = r'(\d+(?:\.\d+)?(?:[-\s]\d+/\d+)?|\d+/\d+)'
INCH_UNIT = r'(?:"|”|″|\s*in(?:ch(?:es)?)?\b)'
SLEEVE_INCHES_RE = re.compile(
    INCH_SIDE + INCH_UNIT + r'?\s*[x×]\s*' + INCH_SIDE + INCH_UNIT, re.IGNORECASE
)
MM_PER_INCH = 25.4


def _inches(side: str) -> float:
    """Read an inch measure such as `2.5`, `2-1/2` or `1/2`."""
    total = 0.0
    for part in re.split(r'[-\s]', side):
        numerator, _, denominator = part.partition('/')
        total += int(numerator) / int(denominator) if denominator else float(numerator)
    return total


def _read_size(text: str) -> str | None:
    """Read a sleeve size from a product description, as `W x Hmm`."""
    match = SLEEVE_SIZE_RE.search(text)
    if match:
        width, height = (float(side.replace(',', '.')) for side in match.groups())
    else:
        match = SLEEVE_INCHES_RE.search(text)
        if not match:
            return None
        width, height = (round(_inches(side) * MM_PER_INCH, 1) for side in match.groups())
    return f'{width:g} x {height:g}mm'


def sized_sleeve_name(shop: Shop, name: str, href: str) -> str | None:
    """Name a sleeve with the size it fits, or None when no size can be found.

    The search results print only a named size ('Standard'), so the size is read
    off the product page and put in the name, where every sleeve's size is read.
    A listing that already has its size stored skips the page.
    """
    if parse_sleeve_size(name):
        logger.info(f'🎲 Sleeve size in name: name={name}')
        return name
    listing = (
        Listing.objects.filter(shop=shop, url=href, sleeve_width__isnull=False)
        .only('sleeve_width', 'sleeve_height')
        .first()
    )
    if listing:
        sized_name = f'{name} ({listing.sleeve_width:g} x {listing.sleeve_height:g}mm)'
        logger.info(f'🎲 Sleeve size already known: name={sized_name}')
        return sized_name

    res = get(href, headers=headers)
    html = BeautifulSoup(res.text, 'html.parser')
    text = ' '.join(
        tag.get_text(' ', strip=True) for tag in html.select('div.desc, div.short_desc')
    )
    size = _read_size(text)
    sized_name = f'{name} ({size})' if size else None
    if not sized_name or not parse_sleeve_size(sized_name):
        logger.warning(f'⚠️ No sleeve size on product page, skipping: name={name}, url={href}')
        return None
    logger.info(f'🎲 Read sleeve size from product page: name={sized_name}')
    return sized_name


def worker(url: str, page: int, category: str | None = None, sleeves: bool = False) -> set[str]:
    """Scrape page, returning the urls of the products it held."""
    logger.info(f' Scraping page {page} '.center(99, '='))
    shop = upsert_shop(shop_name)
    params = {
        'limit': PAGE_SIZE,
        'start': (page - 1) * PAGE_SIZE,
    }
    res = get(url, params=params, headers=headers)
    logger.info(f'🎲 Scraped {res.request.url}...')

    html = BeautifulSoup(res.text, 'html.parser')
    rows = html.select('div.product-box')
    if not rows:
        logger.info(f'🎲 No products on page {page}, stopping: url={url}')
        return set()
    hrefs = set()
    items_handled = 0
    sold_out_count = 0
    hidden_count = 0
    unsized_count = 0
    create_defaults = {'category': category} if category else None
    for row in rows:
        # the visible title is cut short with an ellipsis; its tooltip is whole
        anchor = row.select_one('div.Title a')
        href = shop_host + anchor['href']
        name = re.sub(r'\s*\(New\)$', '', anchor['title'].strip())
        # images load lazily: the real source waits in data-original
        img_src = row.select_one('img.browseProductImage')['data-original']
        hrefs.add(href)
        if ('sleeve' in name.casefold()) != sleeves:
            continue
        # price details
        in_stock = row.select_one('span.vm2-nostock') is None
        if in_stock:
            price_tag = row.select_one('div.wrapper span.PricesalesPrice')
            # some prices are only shown to signed-in shoppers ('Login to View')
            if price_tag is None:
                logger.warning(f'⚠️ No public price, skipping: name={name}, href={href}')
                hidden_count += 1
                continue
            price_value = parse_price(price_tag.get_text(strip=True))
        else:
            sold_out_count += 1
            price_value = None
        if sleeves:
            name = sized_sleeve_name(shop, name, href)
            if name is None:
                unsized_count += 1
                continue

        handle_item_data(
            shop, name, href, img_src, in_stock, price_value, create_defaults=create_defaults
        )
        items_handled += 1

    logger.info(
        f'🎲 Scraped page {page}: hrefs={len(hrefs)}, '
        f'handled={items_handled}, sold_out={sold_out_count}, hidden={hidden_count}, '
        f'unsized={unsized_count}'
    )
    return hrefs


def worker_wrapper(*args, **kwargs):
    """Wrap worker."""
    try:
        return worker(*args, **kwargs)
    except Exception:
        logger.exception('Error during worker')
        raise


def scrape_site():
    """Scrape pages."""
    for url, category, sleeves in urls:
        seen = set()
        page = 0
        while True:
            page += 1
            hrefs = worker(url, page, category=category, sleeves=sleeves)
            seen_before = hrefs <= seen
            seen |= hrefs
            # An offset past the end is served some earlier page again, so a page
            # that is short or carries nothing new is the end of the shelf.
            if not hrefs or seen_before or len(hrefs) < PAGE_SIZE:
                break
        logger.info(
            f'🎲 Scraped shelf: url={url}, category={category}, pages={page}, '
            f'products={len(seen)}'
        )


def scrape():
    """Scrape this site."""
    scrape_site()
    shop = upsert_shop(shop_name)
    missed_listings(shop)
    logger.info(f'🎲 Scraped shop: shop={shop_name}')
