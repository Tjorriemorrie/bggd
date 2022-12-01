import json
import logging
from datetime import datetime
from typing import List

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from django.utils.timezone import now

from main.constants import STOCK_OUT, STOCK_IN, SHOP_NAMES
from main.models import Shop, Price, Day, Game, ShopGame, GameDay
from main.scraper import get

logger = logging.getLogger(__name__)


def update_outdated_game_shop_prices():
    """Update outdated shop prices on games"""
    games = Game.objects.filter(shop_outdated=True).all()
    logger.info(f'Updating {len(games)} outdated shop prices on games')
    for game in games:
        update_game_shop_prices(game)


def update_game_shop_prices(game: Game):
    """
    Update the GameDay with the prices of the best shop.
    Then set the final current value on the game.
    """
    logger.info(f'updating game shop prices for {game}')
    # retrieve all shop prices
    name_shopgames = {}
    dfs = {}
    for shopgame in game.shopgames.all():
        name = shopgame.shop.name.replace(' ', '').lower()
        values = shopgame.prices.filter(status=STOCK_IN).values_list('day__day', 'price')
        if not values:
            continue
        df = pd.DataFrame(values, columns=['day', f'{name}_price'])
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
    for name, df_shop in dfs.items():
        if df is None:
            df = df_shop
        else:
            # df = df.join(df_shop)
            df = pd.merge(df, df_shop, how='outer', left_index=True, right_index=True)
    day = Day.get_today()
    date_range = pd.date_range(
        df.index[0],
        datetime(day.day.year, day.day.month, day.day.day))
    df = df.reindex(date_range)
    for name in dfs:
        df[f'{name}_price'] = df[f'{name}_price'].ffill()
        shopgame = name_shopgames[name]
        last_price = shopgame.prices.last()
        if last_price.status != STOCK_IN:
            oos_day = datetime(last_price.day.day.year, last_price.day.day.month, last_price.day.day.day)
            df.loc[df.index >= oos_day, f'{name}_price'] = np.nan

    df.dropna(axis=0, how='all', inplace=True)
    df['best'] = df.min(axis=1)
    df['mean'] = df['best'].rolling(window=365, min_periods=1).mean()
    df['saving'] = df['mean'] - df['best']

    # clear all game days price values
    GameDay.objects.filter(game=game).update(
        shop_best=None, shop_mean=None, shop_saving=None)

    # update all days for the game
    for index, row in df.iterrows():
        day, day_created = Day.objects.get_or_create(
            day=index,
            defaults={
                'reviews_cnt': 0,
                'reviews_avg': 0,
                'last_review_id': 0,
                'last_review_at': now()})
        if day_created:
            logger.info(f'Created day! {day}')
        gameday, gameday_created = GameDay.objects.get_or_create(
            game=game,
            day=day,
            defaults={
                'reviews_cnt': 0,
                'reviews_avg': 0})
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
    logger.info(f'Updated shop {game.name}: ava={game.shop_available} best={game.shop_price} mean={game.shop_mean} saving={game.shop_saving}')


def validate_shopgames():
    """Ensure shopgames have the correct current availability and price"""
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


def scrape_site(shop: Shop, shopgames: List[ShopGame] = None, fail_fast: bool = False):
    logger.info(f'Scraping {shop}')
    stats = {
        'no url': 0,
        '404': 0,
        'no price': 0,
        'new': 0,
        'no change': 0,
        'errors': 0,
    }
    day = Day.get_today()
    if not shopgames:
        shopgames = shop.shopgames.all()
    else:
        assert all(sg.shop == shop for sg in shopgames)
    for ix, shopgame in enumerate(shopgames):
        # logger.info(f'Progress {ix}/{len(shopgames)}: {shopgame.game}')

        # still scrape games with 0 price (do not use MIA)
        if not shopgame.url:
            stats['no url'] += 1
            continue

        # update current price
        try:
            name = shop.name.lower().replace(' ', '_')
            func = globals()[f'scrape_{name}_game']
            data = func(shopgame.url)
        except Exception as exc:
            if str(exc).startswith('404'):
                logger.info(f'Game removed from store: {shopgame}')
                shopgame.url = None
                shopgame.url_at = now()
                shopgame.mia = True
                shopgame.save()
                stats['404'] += 1
                continue
            logger.exception(f'Could not scrape {shopgame.url}')
            if fail_fast:
                raise
            stats['errors'] += 1
            continue

        # when price is 0 it is not priced
        if not data['price']:
            if not shopgame.mia:
                shopgame.mia = True
                shopgame.save()
            stats['no price'] += 1
            continue

        prev_price = shopgame.prices.last()
        if not prev_price \
                or prev_price.price != data['price'] \
                or prev_price.status != data['status']:
            new_price, _ = Price.objects.update_or_create(
                shopgame=shopgame,
                day=day,
                defaults={
                    'status': data['status'],
                    'price': data['price'],
                }
            )
            logger.info(f'{ix}/{len(shopgames)}: New Price! {new_price}')

            shopgame.current_price = data['price']
            shopgame.current_available = data['status'] == STOCK_IN
            shopgame.mia = False
            shopgame.save()
            stats['new'] += 1

            shopgame.game.shop_outdated = True
            shopgame.game.save()
        else:
            stats['no change'] += 1

    logger.info(f'Finished scraping {shop}: {stats}')


def scrape_meeps_and_veeps_game(url: str) -> dict:
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


def scrape_the_hidden_den_game(url: str) -> dict:
    res = get(url)
    html = BeautifulSoup(res.text, 'html.parser')

    scripts = html.find_all('script')
    scripts = [s for s in scripts if s.get('type', '') == 'application/ld+json']
    details = json.loads(scripts[-1].contents[0])
    price = int(details['@graph'][-1]['offers'][-1]['price'])
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


def scrape_tabletop_guru_game(url: str) -> dict:
    res = get(url)
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
    res = get(url)
    html = BeautifulSoup(res.text, 'html.parser')

    container = html.find('div', class_='w3-display-container')
    price_txt = container.find_all('span', class_='w3-xxlarge')[-1].text
    price_txt = price_txt.replace('R', '').strip()

    status_txt = container.find_all('div')[0].text
    status = STOCK_IN if 'is in stock' in status_txt else STOCK_OUT

    return {
        'status': status,
        'price': int(price_txt),
    }


def scrape_geekhome_game(url: str) -> dict:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',
    }
    res = get(url, headers)
    html = BeautifulSoup(res.text, 'html.parser')

    container = html.find('div', class_='summary entry-summary')
    price_box = container.find('p', class_='price')
    try:
        price_txt = price_box.find('ins').text
    except AttributeError:
        price_txt = price_box.find('bdi').text
    price_txt = price_txt.replace('R', '').replace(',', '').strip()

    status_txt = container.select('p[class*="stock"]')[0].text
    status = STOCK_OUT if any(t in ['Out of stock', 'Available on Backorder'] for t in status_txt) else STOCK_IN

    return {
        'status': status,
        'price': int(float(price_txt)),
    }


def scrape_takealot_game(url: str) -> dict:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',
    }
    res = get(url, headers)
    html = BeautifulSoup(res.text, 'html.parser')

    input_tag = html.find('input', id='id_strike_price')
    price = int(input_tag['value'])
    status = STOCK_IN

    # availability = data['stock_availability']['status']
    # if availability in ['fubar']:
    #     status = STOCK_OUT
    # elif availability in ['In stock', 'Ships in 5 - 7 work days']:
    #     status = STOCK_IN
    # else:
    #     raise NotImplementedError(f'Not sure what is: {availability}')
    # price = data['data_layer']['totalPrice']
    return {
        'status': status,
        'price': price,
    }


###############################################################################################################
# DEPRECATED
###############################################################################################################

def scrape_raru_game(url: str) -> dict:
    res = get(url)
    html = BeautifulSoup(res.text, 'html.parser')

    availability = html.find('div', class_='avail').text
    if availability in ['Out of Stock', 'Not available'] or availability.startswith('Unreleased'):
        status = STOCK_OUT
    elif availability in ['In Stock', 'Dispatched in 30 to 45 working days', 'Dispatched in 25 to 30 working days', 'Dispatched in 20 to 30 working days', 'Dispatched in 15 to 20 working days', 'Dispatched in 10 to 15 working days', 'Dispatched in 10 to 20 working days', 'Dispatched in 7 to 10 working days', 'Dispatched in 5 to 7 working days']:
        status = STOCK_IN
    else:
        raise NotImplementedError(f'Not sure what is: {availability}')
    try:
        price = html.find('dl', class_='price').find('dd').find('span').text.replace(',', '')
    except AttributeError as exc:
        tbc = html.find('dl', class_='price').find('dd').text.strip() == 'TBC'
        price = 0
    return {
        'status': status,
        'price': int(price),
    }
