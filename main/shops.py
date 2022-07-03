import logging
from datetime import datetime
from typing import List

import pandas as pd
from bs4 import BeautifulSoup

from main.constants import SHOP_RARU, STOCK_OUT, STOCK_IN
from main.models import Shop, Price, Day, Game
from main.scraper import get

logger = logging.getLogger(__name__)


def scrape_raru():
    logger.info('Scraping Raru')
    day = Day.get_today()
    shop = Shop.objects.get(name=SHOP_RARU)
    shopgames = shop.shopgames.all()
    for ix, shopgame in enumerate(shopgames):
        logger.info(f'Progress {ix}/{len(shopgames)}: {shopgame.game}')
        if shopgame.mia:
            continue

        # update current price
        try:
            data = scrape_raru_game(shopgame.url)
        except Exception as exc:
            logger.exception(f'Could not scrape {shopgame.url}')
            continue
        # when price is 0 it is not priced
        if not data['price']:
            if not shopgame.mia:
                shopgame.mia = True
                shopgame.save()
            continue
        prev_price = shopgame.prices.last()
        new_price = None
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

        # update stats
        # will only change if there is a new price
        if not shopgame.current_price or new_price:
            values = shopgame.prices.values_list('day__day', 'price')
            df = pd.DataFrame(values, columns=['day', 'price'])
            df['day'] = pd.to_datetime(df['day'])
            df = df.set_index('day')
            date_range = pd.date_range(df.index[0], datetime(day.day.year, day.day.month, day.day.day))
            df = df.reindex(date_range)
            df['price'] = df['price'].ffill()
            shopgame.mean_price = df['price'].mean()
            shopgame.min_price = df['price'].min()
            shopgame.max_price = df['price'].max()
            shopgame.current_price = new_price.price
            shopgame.current_available = new_price.status == STOCK_IN
            shopgame.mean_saving = shopgame.mean_price - shopgame.current_price
            shopgame.save()

            # then update game
            aggregate_shop(shopgame.game)

    logger.info('Finished scraping Raru')


def scrape_raru_game(url: str) -> dict:
    res = get(url)
    html = BeautifulSoup(res.text, 'html.parser')

    availability = html.find('div', class_='avail').text
    if availability in ['Out of Stock'] or availability.startswith('Unreleased'):
        status = STOCK_OUT
    elif availability in ['In Stock', 'Dispatched in 25 to 30 working days', 'Dispatched in 20 to 30 working days', 'Dispatched in 10 to 15 working days', 'Dispatched in 10 to 20 working days', 'Dispatched in 7 to 10 working days', 'Dispatched in 5 to 7 working days']:
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


def aggregate_shop(game: Game):
    best_shopgame = game.best_shop()
    if not best_shopgame or not best_shopgame.current_available:
        game.shop_available = False
    else:
        game.shop_available = True
        game.shop_price = best_shopgame.current_price
        game.shop_saving = best_shopgame.mean_saving
    game.save()
