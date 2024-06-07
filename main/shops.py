import json
import logging
import re
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from django.utils.timezone import now

from main.constants import MINIMUM_GAME_PRICE, SHOP_BGBSA, SHOP_NAMES, STOCK_IN, STOCK_OUT
from main.errors import ShopGameNotFoundError
from main.models import Day, Game, GameDay, Price, Shop, ShopGame
from main.scraper import RedirectError, get

logger = logging.getLogger(__name__)


def update_outdated_game_shop_prices():
    """Update outdated shop prices on games."""
    games = Game.objects.filter(shop_outdated=True).all()
    logger.info(f'Updating {len(games)} outdated shop prices on games')
    for game in games:
        update_game_shop_prices(game)


def update_game_shop_prices(game: Game):  # noqa PLR0915 PLR0912
    """Update the GameDay with the prices of the best shop.

    Then set the final current value on the game.
    """
    logger.info(f'updating game shop prices for {game}')
    # retrieve all shop prices
    name_shopgames = {}
    dfs = {}
    for shopgame in game.shopgames.all():
        name = shopgame.shop.name.replace(' ', '').lower()
        values = shopgame.prices.values_list('day__day', 'price', 'status')
        if not values:
            continue
        df = pd.DataFrame(values, columns=['day', f'{name}_price', f'{name}_status'])
        df['day'] = pd.to_datetime(df['day'])
        df = df.set_index('day')
        dfs[name] = df
        name_shopgames[name] = shopgame

    if not dfs:
        game.shop_available = False
        game.shop_price = None
        game.shop_mean = None
        game.shop_saving = None
        game.shop_outdated = False
        game.shop_updated_at = now()
        game.save()
        logger.info(f'No shop {game.name}: ava={game.shop_available}')
        return

    # build best shop price per day
    # df = pd.concat(dfs.values())
    df = None
    for df_shop in dfs.values():
        if df is None:
            df = df_shop
        else:
            # df = df.join(df_shop)
            df = pd.merge(df, df_shop, how='outer', left_index=True, right_index=True)
    day = Day.get_today()
    date_range = pd.date_range(df.index[0], datetime(day.day.year, day.day.month, day.day.day))
    df = df.reindex(date_range)
    for name in dfs:
        df[f'{name}_price'] = df[f'{name}_price'].ffill()
        df[f'{name}_status'] = df[f'{name}_status'].ffill()
        df.loc[df[f'{name}_status'] == STOCK_OUT, f'{name}_price'] = np.nan
        df.drop(f'{name}_status', axis=1, inplace=True)

    df.dropna(axis=0, how='all', inplace=True)
    df['best'] = df.min(axis=1)
    df['mean'] = df['best'].rolling(window=365, min_periods=1).mean()
    df['saving'] = df['mean'] - df['best']

    # clear all game days price values
    GameDay.objects.filter(game=game).update(shop_best=None, shop_mean=None, shop_saving=None)

    # update all days for the game
    for index, row in df.iterrows():
        day, day_created = Day.objects.get_or_create(
            day=index,
            defaults={
                'reviews_cnt': 0,
                'reviews_avg': 0,
                'last_review_id': 0,
                'last_review_at': now(),
            },
        )
        if day_created:
            logger.info(f'Created day! {day}')
        gameday, gameday_created = GameDay.objects.get_or_create(
            game=game, day=day, defaults={'reviews_cnt': 0, 'reviews_avg': 0}
        )
        if gameday_created:
            logger.info(f'Created gameday! {gameday}')
        gameday.shop_best = row['best']
        gameday.shop_mean = row['mean']
        gameday.shop_saving = int(round(row['saving'] / 10) * 10)
        gameday.save()

    # finally update game
    best_shop = game.best_shop()
    if best_shop:
        game.shop_available = True
        game.shop_price = best_shop.current_price
        latest_gameday = GameDay.objects.filter(game=game).latest('day__day')
        game.shop_mean = latest_gameday.shop_mean
        game.shop_saving = latest_gameday.shop_saving
    else:
        game.shop_available = False
        game.shop_price = None
        game.shop_mean = None
        game.shop_saving = None
    game.shop_outdated = False
    game.shop_updated_at = now()
    game.save()
    logger.info(
        f'Updated shop {game.name}: ava={game.shop_available} best={game.shop_price} '
        f'mean={game.shop_mean} saving={game.shop_saving}'
    )


def validate_shopgames():
    """Ensure shopgames have the correct current availability and price."""
    logger.info('Validating all shopgames...')
    for shop_name in SHOP_NAMES:
        shop = Shop.objects.get(name=shop_name)
        logger.info(f'Validating {shop}')
        shopgames = ShopGame.objects.prefetch_related('prices').filter(shop=shop).all()
        for shopgame in shopgames:
            try:
                last_price = shopgame.prices.latest('day__day')
            except Price.DoesNotExist:
                last_price = None
            current_price = last_price.price if last_price else None
            current_available = last_price.status == STOCK_IN if last_price else None
            mia = False if current_available and current_price else shopgame.mia
            if (
                shopgame.current_price != current_price
                or shopgame.current_available != current_available
                or shopgame.mia != mia
            ):
                shopgame.current_price = current_price
                shopgame.current_available = current_available
                shopgame.mia = mia
                shopgame.save()
                logger.info(f'Fixed broken {shopgame}')


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


def upsert_new_price(
    ix: int, shopgame: ShopGame, shopgames: list[ShopGame], data: dict, stats: dict
):
    """Upsert new price if different."""
    day = Day.get_today()
    prev_price = shopgame.prices.last()
    if not prev_price or prev_price.price != data['price'] or prev_price.status != data['status']:
        new_price, _ = Price.objects.update_or_create(
            shopgame=shopgame,
            day=day,
            defaults={
                'status': data['status'],
                'price': data['price'],
            },
        )
        logger.info(f'{ix}/{len(shopgames)}: New Price! {new_price}')

        shopgame.current_price = (
            data['price'] if data['price'] else prev_price.price if prev_price else data['price']
        )
        shopgame.current_available = data['status'] == STOCK_IN
        shopgame.mia = not bool(shopgame.url)
        shopgame.save()
        stats['new'] += 1

        shopgame.game.shop_outdated = True
        shopgame.game.save()
    else:
        stats['no change'] += 1


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
    res = get(url)
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

    script = html.find('script', id='ProductJson-product-template')
    details = json.loads(script.contents[0])

    price = details['price'] // 100
    if 'ORDER BY' in details['title']:
        price /= 0.30
    status = STOCK_IN if details['available'] else STOCK_OUT

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


def scrape_level_up_game(url: str) -> dict:
    """Scrape Level Up."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    res = get(url, headers, redirect=False)
    html = BeautifulSoup(res.text, 'html.parser')
    container = html.select_one('div[class*=product-block--price]')
    sold_out_tag = container.find('span', text='Sold Out')
    if sold_out_tag:
        status = STOCK_OUT
        price_txt = 0
    else:
        status = STOCK_IN
        price_box = container.select_one('span[class*=price]')
        price_txt = price_box.text
        price_txt = price_txt.replace('R', '').replace(',', '').strip()

    return {
        'status': status,
        'price': int(float(price_txt)),
    }


def scrape_amazon_game(url: str) -> dict:
    """Scrape Amazon."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
    }
    res = get(url, headers)
    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('form', id='addToCart')

    price_txt = container.find('span', class_='a-price-whole').text
    price_txt = price_txt.replace('R', '').replace(',', '').strip()

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
    res = get(shop.host)
    html = BeautifulSoup(res.text, 'html.parser')
    container = html.find('div', id='fbody')
    items = container.find_all('div', class_='card')
    total = len(items)
    for ix, item in enumerate(items):
        stoid = item.get('stoid')
        url = f'https://www.bgbsa.co.za/contactbuy.php?id={stoid}'
        res_detail = get(url)
        html_detail = BeautifulSoup(res_detail.text, 'html.parser')

        pattern_url = re.compile(r'https://boardgamegeek.com/boardgame/.*')
        tag_with_url = html_detail.find_all(string=pattern_url)[0]
        bgg_id = int(tag_with_url.text.split('/')[-1])
        try:
            game = Game.objects.get(bgg_id=bgg_id)
        except Game.DoesNotExist:
            logger.info(f'{ix}/{total}: [{stoid}] game not found')
            stats['404'] += 1
            continue

        pattern_price = re.compile(r'R\s*[\d,.]+')
        tag_with_price = html_detail.find_all(string=pattern_price)[0]
        price_cleaned = re.sub(r'[^\d.]', '', tag_with_price.text)
        price = int(float(price_cleaned))
        if price < MINIMUM_GAME_PRICE:
            stats['no price'] += 1
            continue

        shopgame, _ = ShopGame.objects.update_or_create(
            shop=shop,
            game=game,
            defaults={
                'url': url,
                'url_at': now(),
            },
        )
        data = {
            'price': price,
            'status': STOCK_IN,
        }
        upsert_new_price(ix, shopgame, items, data, stats)

    # update shopgames as out of stock when not found (url would be timestamped)
    two_days = now() - timedelta(days=2)
    shopgames_outdated = ShopGame.objects.filter(shop=shop, url_at__lt=two_days).all()
    for ix, outdated in enumerate(shopgames_outdated):
        data = {'price': 0, 'status': STOCK_OUT}
        upsert_new_price(ix, outdated, shopgames_outdated, data, stats)

    logger.info(f'Finished scraping {shop}: {stats}')
