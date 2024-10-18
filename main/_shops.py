import concurrent
import json
import logging
import re
import time
from datetime import timedelta

from bs4 import BeautifulSoup
from django.conf import settings
from django.db import OperationalError
from django.utils.timezone import now
from retry import retry

from main.constants import MINIMUM_GAME_PRICE, SHOP_BGBSA, STOCK_IN, STOCK_OUT
from main.errors import ShopGameNotFoundError
from main.games import RedirectError, get
from main.models import Game, Shop, ShopGame

logger = logging.getLogger(__name__)


######################################################################################


def scrape_site(shop: Shop, shopgames: list[ShopGame] = None, fail_fast: bool = False):  # noqa PLR0912
    """Scrape a site."""
    logger.info(f'Scraping {shop}')
    stats = {
        'no url': 0,
        '404': 0,
        'no price': 0,
        'new': 0,
        'no change': 0,
        'errors': 0,
    }

    if shop.name == SHOP_BGBSA:
        return scrape_bgbsa()
    elif not shopgames:
        shopgames = shop.shopgames.all()
    else:
        assert all(sg.shop == shop for sg in shopgames)  # noqa S101

    for ix, shopgame in enumerate(shopgames):
        # logger.info(f'Progress {ix}/{len(shopgames)}: {shopgame.game}')

        # still scrape games with 0 price (do not use MIA)
        if not shopgame.url:
            stats['no url'] += 1
            # ensure the game is listed as not available (when url is removed)
            upsert_new_price(ix, shopgame, shopgames, {'price': 0, 'status': STOCK_OUT}, stats)
            continue

        # update current price
        try:
            name = shop.name.lower().replace(' ', '_')
            func = globals()[f'scrape_{name}_game']
            data = func(shopgame.url)
        except ShopGameNotFoundError:
            shopgame.mark_as_removed()
            stats['404'] += 1
            if fail_fast:
                raise
            continue
        except Exception as exc:
            if str(exc).startswith('404'):
                shopgame.mark_as_removed()
                stats['404'] += 1
                if fail_fast:
                    raise
                continue
            logger.exception(f'Could not scrape {shopgame.url}')
            stats['errors'] += 1
            if fail_fast:
                raise
            continue

        # when price is 0 it is not priced (but still need to save new price that it is oos)
        if not data['price'] or data['price'] < MINIMUM_GAME_PRICE:
            stats['no price'] += 1

        upsert_new_price(ix, shopgame, shopgames, data, stats)

    logger.info(f'Finished scraping {shop}: {stats}')


def scrape_meeps_and_veeps_game(url: str) -> dict:
    """Scrape meeps and veeps."""
    res = get(url)
    html = BeautifulSoup(res.text, 'html.parser')

    json_text = html.find('script', id='ProductJson-product-template')
    details = json.loads(json_text.contents[0])
    price = details['price'] // 100
    status = STOCK_IN if details['available'] else STOCK_OUT

    return {
        'status': status,
        'price': price,
    }


def scrape_grinning_gargoyle_game(url: str) -> dict:
    """Scrape grinning gargoyle."""
    res = get(url)
    html = BeautifulSoup(res.text, 'html.parser')

    scripts = html.find_all('script')
    scripts = [s for s in scripts if s.get('type', '') == 'application/ld+json']
    details = json.loads(scripts[-1].contents[0])
    price = int(float(details['@graph'][-1]['offers'][-1]['price']))
    if 'InStock' in details['@graph'][-1]['offers'][-1]['availability']:
        status = STOCK_IN
    elif 'BackOrder' in details['@graph'][-1]['offers'][-1]['availability']:
        status = STOCK_OUT
        price_tag = html.find(text=re.compile(r'Estimate RRP: R\d+(\.\d{2})?'))
        if price_tag:
            match = re.search(r'R(\d+(\.\d{2})?)', price_tag.text)
            if match:
                price = float(match.group(1))
    elif 'OutOfStock' in details['@graph'][-1]['offers'][-1]['availability']:
        status = STOCK_OUT
    else:
        raise ValueError(f'Unknown availability: {details["@graph"][-1]["offers"]}')

    return {
        'status': status,
        'price': price,
    }


def scrape_the_hidden_den_game(url: str) -> dict:
    """Scrape the hidden den."""
    try:
        res = get(url, redirect=False)
    except RedirectError as exc:
        logger.error(f'Product not found for {url}')
        raise ShopGameNotFoundError() from exc

    html = BeautifulSoup(res.text, 'html.parser')
    scripts = html.find_all('script')
    scripts = [s for s in scripts if s.get('type', '') == 'application/ld+json']
    details = json.loads(scripts[-1].contents[0])

    # price sometimes #N/A with no stock given
    if '@graph' not in details:
        raise ShopGameNotFoundError(f'No graph in details for {url}')

    price = int(float(details['@graph'][-1]['offers'][-1]['price']))
    if 'InStock' in details['@graph'][-1]['offers'][-1]['availability']:
        status = STOCK_IN
    elif 'OutOfStock' in details['@graph'][-1]['offers'][-1]['availability']:
        status = STOCK_OUT
    elif 'BackOrder' in details['@graph'][-1]['offers'][-1]['availability']:
        status = STOCK_IN
    else:
        raise ValueError(f'Unknown availability: {details["@graph"][-1]["offers"]}')

    return {
        'status': status,
        'price': price,
    }


def scrape_tabletop_guru_game(url: str) -> dict:
    """Scrape tabletop guru."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    try:
        res = get(url, headers, redirect=False)
    except RedirectError as exc:
        logger.error(f'Product not found for {url}')
        raise ShopGameNotFoundError() from exc
    html = BeautifulSoup(res.text, 'html.parser')
    if '404 Page Not Found' in html.text:
        logger.error(f'Product not found for {url}')
        raise ShopGameNotFoundError('404 text on page')
    script = html.find('script', id='ProductJson-product-template')
    details = json.loads(script.contents[0])

    status = STOCK_IN if details['available'] else STOCK_OUT

    price = details['price'] // 100
    if 'ORDER BY' in details['title']:
        price /= 0.30
        status = STOCK_OUT

    return {
        'status': status,
        'price': price,
    }


def scrape_timeless_game(url: str) -> dict:
    """Scrape timeless."""
    res = get(url)
    html = BeautifulSoup(res.text, 'html.parser')

    if 'Product not found.' in html.text:
        logger.error(f'Product not found for {url}')
        raise ShopGameNotFoundError()

    containers = html.find_all('div', class_='w3-display-container')
    container = containers[-1]
    price_boxes = container.find_all('span', class_='w3-xxlarge')

    try:
        price_txt = price_boxes[-1].text
        price_txt = price_txt.replace('R', '').strip()
    except IndexError:
        # page exists, but price does not show for out of stock games
        price_txt = '0'

    status_txt = container.find_all('div')[0].text
    status = STOCK_IN if 'is in stock' in status_txt else STOCK_OUT

    return {
        'status': status,
        'price': int(price_txt),
    }


def scrape_geekhome_game(url: str) -> dict:
    """Scrape geekhome."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    try:
        res = get(url, headers, redirect=False)
    except RedirectError as exc:
        logger.error(f'Product not found for {url}')
        raise ShopGameNotFoundError() from exc

    html = BeautifulSoup(res.text, 'html.parser')
    if 'It looks like nothing was found at this location' in html.text:
        logger.error(f'Product not found for {url}')
        raise ShopGameNotFoundError('404 text on page')

    container = html.find('div', class_='summary entry-summary')
    price_box = container.find('p', class_='price')
    try:
        price_txt = price_box.find('ins').text
    except AttributeError:
        price_txt = price_box.find('bdi').text
    price_txt = price_txt.replace('R', '').replace(',', '').strip()

    status_txt = container.select('p[class*="stock"]')[0].text
    status = (
        STOCK_OUT
        if any(t in ['Out of stock', 'Available on Backorder'] for t in status_txt)
        else STOCK_IN
    )

    return {
        'status': status,
        'price': int(float(price_txt)),
    }


def scrape_sword_and_board_game(url: str) -> dict:
    """Scrape Sword and board."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    res = get(url, headers, redirect=False)
    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('div', class_='product-single__meta')
    price_box = container.find('div', class_='price-product')
    price_box = price_box.select_one('span[class*=product-price__price]')
    price_txt = price_box.text
    price_txt = price_txt.replace('R', '').replace(',', '').strip()

    status_box = container.find('div', id='sold-out')
    status = STOCK_OUT if status_box else STOCK_IN

    return {
        'status': status,
        'price': int(float(price_txt)),
    }


def scrape_amazon_game(url: str) -> dict:
    """Scrape Amazon."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa: E501
    }
    res = get(url, headers)
    html = BeautifulSoup(res.text, 'html.parser')

    if 'The Web address you entered is not a functioning page on our site' in html.text:
        raise ShopGameNotFoundError('Product page missing')

    if any(
        t in html.text
        for t in ['No featured offers available', 'Currently unavailable', 'See All Buying Options']
    ):  # noqa: E501
        price_txt = '0'
        status = STOCK_OUT

    else:
        container = html.find('form', id='addToCart')
        if not container:
            raise ValueError('Could not find form #addToCart')
        price_tag = container.find('span', class_='a-price-whole')
        if not price_tag:
            raise ValueError('Could not find price span.a-price-whole')
        price_txt = price_tag.text.replace('R', '').replace(',', '').strip()
        status = STOCK_OUT if 'out of stock' in container.text else STOCK_IN

    return {
        'status': status,
        'price': int(float(price_txt)),
    }


def scrape_bgbsa():
    """Scrape BGBSA."""
    logger.info('Scraping BGBSA...')
    stats = {
        'no url': 0,
        '404': 0,
        'no price': 0,
        'new': 0,
        'no change': 0,
        'errors': 0,
    }
    shop = Shop.objects.get(name=SHOP_BGBSA)
    headers = {'Authorization': f'Bearer {settings.BGBSA_BEARER}'}
    res = get(f'{shop.shop_host}api/all.json', headers=headers)
    data = res.json()['listings']

    started_at = time.time()
    max_workers = 1 if settings.DEBUG else 6
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(bgbsa_worker, ix, data, item, stats) for ix, item in enumerate(data)
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception:
                logger.exception(f'Worker failed for {future}')

    ended_at = time.time()
    logger.info(f'total time = {(ended_at - started_at):.0f}')

    # update shopgames as out of stock when not found (url would be timestamped)
    two_days = now() - timedelta(days=2)
    shopgames_outdated = ShopGame.objects.filter(shop=shop, url_at__lt=two_days).all()
    for ix, outdated in enumerate(shopgames_outdated):
        data = {'price': 0, 'status': STOCK_OUT}
        upsert_new_price(ix, outdated, shopgames_outdated, data, stats)

    logger.info(f'Finished scraping {shop}: {stats}')


def bgbsa_worker(ix: int, data: list, item: str, stats: dict):
    """Threading worker for bgbsa."""
    total = len(data)
    try:
        game = get_game(item['games'][0]['bgg_id'])
    except Game.DoesNotExist:
        logger.info(f'{ix}/{total}: [{item}] game not found')
        stats['404'] += 1
        return

    price = float(item['price'])
    if price < MINIMUM_GAME_PRICE:
        stats['no price'] += 1
        return

    shopgame = upsert_shopgame(game, item['url'])
    values = {
        'price': price,
        'status': STOCK_IN if item['state'] == 'active' else STOCK_OUT,
    }
    upsert_new_price(ix, shopgame, data, values, stats)
    logger.info(f'{ix}/{total}: [{game.shop_name} @ {item["price"]}] game done')


@retry((OperationalError,), tries=99, delay=1, backoff=1, jitter=1, max_delay=30, logger=logger)
def get_game(bgg_id: int) -> Game:
    """Get game with retries."""
    return Game.objects.get(bgg_id=bgg_id)


@retry((OperationalError,), tries=99, delay=1, backoff=1, jitter=1, max_delay=30, logger=logger)
def upsert_shopgame(game: Game, url: str) -> ShopGame:
    """Upsert shopgame with retries."""
    shop = Shop.objects.get(name=SHOP_BGBSA)
    shopgame, _ = ShopGame.objects.update_or_create(
        shop=shop,
        game=game,
        defaults={
            'url': url,
            'url_at': now(),
        },
    )
    return shopgame
