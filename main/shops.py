import json
import logging
from datetime import datetime
from typing import List

import pandas as pd
from bs4 import BeautifulSoup
from django.utils.timezone import now
from pandas import DataFrame

from main.constants import SHOP_RARU, STOCK_OUT, STOCK_IN, SHOP_TAKEALOT, \
    SHOP_MEEPS_AND_VEEPS, SHOP_TIMELESS, SHOP_GEEKHOME
from main.models import Shop, Price, Day, Game, ShopGame
from main.scraper import get

logger = logging.getLogger(__name__)


def update_shopgame_stats(shopgame: ShopGame):
    """
    Get stats from in-stock prices.
    Update current data from a new price
    Aggregate the shop when new price or in stock.
    """
    df = calc_shopgame_stats(shopgame)
    shopgame.mean_price = df['price'].mean()
    shopgame.min_price = df['price'].min()
    shopgame.max_price = df['price'].max()

    last_price = shopgame.prices.last()
    shopgame.current_available = last_price.status == STOCK_IN
    shopgame.current_price = last_price.price
    saving = shopgame.mean_price - shopgame.current_price
    shopgame.mean_saving = int(round(saving / 10) * 10)

    shopgame.save()

    # then update game
    aggregate_game_shops(shopgame.game)


def calc_shopgame_stats(shopgame: ShopGame) -> DataFrame:
    values = shopgame.prices.filter(status=STOCK_IN).values_list('day__day', 'price')
    if not values:
        values = shopgame.prices.values_list('day__day', 'price')
    df = pd.DataFrame(values, columns=['day', 'price'])
    df['day'] = pd.to_datetime(df['day'])
    df = df.set_index('day')
    day = Day.get_today()
    date_range = pd.date_range(
        df.index[0],
        datetime(day.day.year, day.day.month, day.day.day))
    df = df.reindex(date_range)
    df['price'] = df['price'].ffill()
    return df


def aggregate_game_shops(game: Game):
    """Update the game with the best shop values. The best shop is selected
    by having the lowest current price and can be put directly on the game.
    The mean saving needs to be calculated across all shops where it is
    active (the current best shop should at least be selected)."""
    best_shopgame = game.best_shop()
    if not best_shopgame:
        game.shop_available = False
    else:
        game.shop_available = True
        game.shop_price = best_shopgame.current_price
        best_mean_price_shop = game.best_shop_mean_price()
        mean_saving = best_mean_price_shop.mean_price - best_shopgame.current_price
        game.shop_saving = mean_saving
    game.save()


def scrape_raru(shopgames: List[ShopGame] = None, fail_fast: bool = False):
    logger.info(f'Scraping {SHOP_RARU}')
    day = Day.get_today()
    shop = Shop.objects.get(name=SHOP_RARU)
    if not shopgames:
        shopgames = shop.shopgames.all()
    else:
        assert all(sg.shop.name == SHOP_RARU for sg in shopgames)
    for ix, shopgame in enumerate(shopgames):
        # logger.info(f'Progress {ix}/{len(shopgames)}: {shopgame.game}')
        if shopgame.mia:
            continue

        # update current price
        try:
            data = scrape_raru_game(shopgame.url)
        except Exception as exc:
            logger.exception(f'Could not scrape {shopgame.url}')
            if fail_fast:
                raise
            continue
        # when price is 0 it is not priced
        if not data['price']:
            if not shopgame.mia:
                shopgame.mia = True
                shopgame.save()
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

        # update shopgame stats
        update_shopgame_stats(shopgame)

    logger.info(f'Finished scraping {SHOP_RARU}')


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


def scrape_takealot(shopgames: List[ShopGame] = None, fail_fast: bool = False):
    logger.info(f'Scraping {SHOP_TAKEALOT}')
    day = Day.get_today()
    shop = Shop.objects.get(name=SHOP_TAKEALOT)
    if not shopgames:
        shopgames = shop.shopgames.all()
    else:
        assert all(sg.shop.name == SHOP_TAKEALOT for sg in shopgames)
    for ix, shopgame in enumerate(shopgames):
        logger.info(f'Progress {ix}/{len(shopgames)}: {shopgame.game}')
        if shopgame.mia:
            continue

        # update current price
        try:
            data = scrape_takealot_game(shopgame.url)
        except Exception as exc:
            logger.exception(f'Could not scrape {shopgame.url}')
            if fail_fast:
                raise
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
            logger.info(f'New Price! {new_price}')

        # update shopgame stats
        update_shopgame_stats(shopgame)

    logger.info(f'Finished scraping {SHOP_TAKEALOT}')


def scrape_takealot_game(url: str) -> dict:
    plid = url.split('/')[-1]
    api_url = f'https://api.takealot.com/rest/v-1-10-0/product-details/{plid}?platform=desktop&display_credit=true'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',
    }
    res = get(api_url, headers)
    data = res.json()

    availability = data['stock_availability']['status']
    if availability in ['fubar']:
        status = STOCK_OUT
    elif availability in ['In stock', 'Ships in 5 - 7 work days']:
        status = STOCK_IN
    else:
        raise NotImplementedError(f'Not sure what is: {availability}')
    price = data['data_layer']['totalPrice']
    return {
        'status': status,
        'price': price,
    }


def scrape_meeps_and_veeps(shopgames: List[ShopGame] = None, fail_fast: bool = False):
    logger.info(f'Scraping {SHOP_MEEPS_AND_VEEPS}')
    day = Day.get_today()
    shop = Shop.objects.get(name=SHOP_MEEPS_AND_VEEPS)
    if not shopgames:
        shopgames = shop.shopgames.all()
    else:
        assert all(sg.shop.name == SHOP_MEEPS_AND_VEEPS for sg in shopgames)
    for ix, shopgame in enumerate(shopgames):
        # logger.info(f'Progress {ix}/{len(shopgames)}: {shopgame.game}')

        # still scrape games with 0 price (do not use MIA)
        if not shopgame.url:
            continue

        # update current price
        try:
            data = scrape_meeps_and_veeps_game(shopgame.url)
        except Exception as exc:
            logger.exception(f'Could not scrape {shopgame.url}')
            if fail_fast:
                raise
            continue
        # when price is 0 it is not priced
        if not data['price']:
            if not shopgame.mia:
                shopgame.mia = True
                shopgame.save()
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

        # update shopgame stats
        update_shopgame_stats(shopgame)

    logger.info(f'Finished scraping {SHOP_MEEPS_AND_VEEPS}')


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


def scrape_timeless(shopgames: List[ShopGame] = None, fail_fast: bool = False):
    logger.info(f'Scraping {SHOP_TIMELESS}')
    day = Day.get_today()
    shop = Shop.objects.get(name=SHOP_TIMELESS)
    if not shopgames:
        shopgames = shop.shopgames.all()
    else:
        assert all(sg.shop.name == SHOP_TIMELESS for sg in shopgames)
    for ix, shopgame in enumerate(shopgames):
        # logger.info(f'Progress {ix}/{len(shopgames)}: {shopgame.game}')

        # still scrape games with 0 price (do not use MIA)
        if not shopgame.url:
            continue

        # update current price
        try:
            data = scrape_timeless_game(shopgame.url)
        except Exception as exc:
            logger.exception(f'Could not scrape {shopgame.url}')
            if fail_fast:
                raise
            continue
        # when price is 0 it is not priced
        if not data['price']:
            if not shopgame.mia:
                shopgame.mia = True
                shopgame.save()
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

        # update shopgame stats
        update_shopgame_stats(shopgame)

    logger.info(f'Finished scraping {SHOP_TIMELESS}')


def scrape_timeless_game(url: str) -> dict:
    res = get(url)
    html = BeautifulSoup(res.text, 'html.parser')

    container = html.find('div', class_='w3-display-container')
    price_txt = container.find_all('span', class_='w3-xxlarge')[0].text
    price_txt = price_txt.replace('R', '').strip()

    status_txt = container.find_all('div')[0].text
    status = STOCK_IN if 'is in stock' in status_txt else STOCK_OUT

    return {
        'status': status,
        'price': int(price_txt),
    }


def scrape_geekhome(shopgames: List[ShopGame] = None, fail_fast: bool = False):
    logger.info(f'Scraping {SHOP_GEEKHOME}')
    day = Day.get_today()
    shop = Shop.objects.get(name=SHOP_GEEKHOME)
    if not shopgames:
        shopgames = shop.shopgames.all()
    else:
        assert all(sg.shop.name == SHOP_GEEKHOME for sg in shopgames)
    for ix, shopgame in enumerate(shopgames):
        # logger.info(f'Progress {ix}/{len(shopgames)}: {shopgame.game}')

        # still scrape games with 0 price (do not use MIA)
        if not shopgame.url:
            continue

        # update current price
        try:
            data = scrape_geekhome_game(shopgame.url)
        except Exception as exc:
            if str(exc).startswith('404'):
                logger.info(f'Game removed from store: {shopgame}')
                shopgame.url = None
                shopgame.url_at = now()
                shopgame.mia = True
                shopgame.save()
                continue
            logger.exception(f'Could not scrape {shopgame.url}')
            if fail_fast:
                raise
            continue
        # when price is 0 it is not priced
        if not data['price']:
            if not shopgame.mia:
                shopgame.mia = True
                shopgame.save()
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

        # update shopgame stats
        update_shopgame_stats(shopgame)

    logger.info(f'Finished scraping {SHOP_GEEKHOME}')


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
