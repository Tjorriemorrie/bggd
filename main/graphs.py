import logging
from datetime import datetime
from itertools import combinations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from django.db.models import Q

from main.constants import SHOP_NAMES, STOCK_OUT
from main.models import Day, Game, Shop, ShopGame

logger = logging.getLogger(__name__)


def get_game_prices_bar(game: Game):
    """Get game prices in bar chart for every shop."""
    logger.info(f'Getting price graph for {game}')
    fig = go.Figure()
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
    df = None
    for df_shop in dfs.values():
        if df is None:
            df = df_shop
        else:
            df = pd.merge(df, df_shop, how='outer', left_index=True, right_index=True)
    if df.empty:
        return
    today = Day.get_today()
    date_range = pd.date_range(
        df.index[0], datetime(today.day.year, today.day.month, today.day.day)
    )
    df = df.reindex(date_range)
    for name in dfs:
        df[f'{name}_price'] = df[f'{name}_price'].ffill()
        df[f'{name}_status'] = df[f'{name}_status'].ffill()
        df.loc[df[f'{name}_status'] == STOCK_OUT, f'{name}_price'] = np.nan
        fig.add_scatter(x=df.index, y=df[f'{name}_price'], mode='lines', name=name)
    fig.update_layout(
        title='Prices from Shops', xaxis_title='Date', yaxis_title='Price', legend_title='Shop Name'
    )
    return fig


def get_shop_sizes():
    """Get shop sizes graph."""
    df_data = []
    for shop_name in SHOP_NAMES:
        shop = Shop.objects.get(name=shop_name)
        qs = ShopGame.objects.filter(shop=shop).filter(
            mia=False, url__isnull=False, current_available=True
        )
        df_data.append({'shop': shop_name, 'in stock': qs.count()})
    df = pd.DataFrame(df_data)
    fig_shop_size = px.bar(df, x='shop', y='in stock', title='Shop size')
    return fig_shop_size


def get_shop_comparison():
    """Get shop prices comparison."""
    data = {}
    combs = list(combinations(SHOP_NAMES, 2))
    for name1, name2 in combs:
        if name1 not in data:
            data[name1] = {}
        if name2 not in data:
            data[name2] = {}

        shopgames_1 = (
            ShopGame.objects.filter(shop__name=name1)
            .exclude(Q(current_available=False) | Q(mia=True))
            .values_list('game', flat=True)
        )
        shopgames_2 = (
            ShopGame.objects.filter(shop__name=name2)
            .exclude(Q(current_available=False) | Q(mia=True))
            .values_list('game', flat=True)
        )
        game_ids = set(shopgames_1) & set(shopgames_2)
        logger.info(f'Found {len(game_ids)} between {name1} and {name2}')

        if not game_ids:
            data[name1][name2] = 0
            data[name2][name1] = 0
            continue

        shop_1_diffs = []
        shop_2_diffs = []
        for game_id in game_ids:
            shopgame_1 = ShopGame.objects.get(shop__name=name1, game__id=game_id)
            shopgame_2 = ShopGame.objects.get(shop__name=name2, game__id=game_id)
            shop_1_diffs.append(shopgame_2.current_price - shopgame_1.current_price)
            shop_2_diffs.append(shopgame_1.current_price - shopgame_2.current_price)
        shop_1 = sum(shop_1_diffs) / len(shop_1_diffs)
        shop_2 = sum(shop_2_diffs) / len(shop_2_diffs)
        data[name1][name2] = shop_1
        data[name2][name1] = shop_2

    formatted = {}
    for name in SHOP_NAMES:
        formatted[name] = [data[name].get(s, 0) for s in SHOP_NAMES]
        formatted[name].append(sum(formatted[name]))

    return formatted
