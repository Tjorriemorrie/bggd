import logging
from collections import Counter
from datetime import datetime
from itertools import combinations
from statistics import mean, median

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from django.db.models import Count

from main.constants import SHOP_NAMES, STOCK_OUT
from main.models import Day, Game, Player, Review, Shop, ShopGame

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
    fig_shop_size = px.bar(df, x='shop', y='in stock', title='Shop size', height=600)
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

        shopgames_1 = ShopGame.objects.filter(shop__name=name1, current_available=True).values_list(
            'game', flat=True
        )
        shopgames_2 = ShopGame.objects.filter(shop__name=name2, current_available=True).values_list(
            'game', flat=True
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
        data[name1][name2] = mean(shop_1_diffs)
        data[name2][name1] = mean(shop_2_diffs)

    formatted = {}
    for name in SHOP_NAMES:
        formatted[name] = [data[name].get(s, 0) for s in SHOP_NAMES]
        formatted[name].append(median(formatted[name]))

    sorted_formatted = dict(sorted(formatted.items(), key=lambda item: item[1][-1], reverse=True))

    return sorted_formatted


def get_reviews_daily_count_graph():
    """Get reviews of daily count in graph."""
    days = Day.objects.order_by('-day').all()[:90]
    data_day = [{'Date': d.day, 'Ratings': d.reviews_cnt} for d in days]
    df = pd.DataFrame(data_day)
    df['Date'] = pd.to_datetime(df['Date'])
    fig = px.bar(
        df,
        x='Date',
        y='Ratings',
        labels={'Ratings': '# of ratings'},
        title='Ratings past quarter',
    )
    return fig


def get_reviews_histogram_ratings():
    """Get reviews histogram ratings."""
    histogram = Review.objects.values('rating').annotate(cnt=Count('rating'))
    df = pd.DataFrame(list(histogram))
    fig = px.histogram(
        df,
        x='rating',
        y='cnt',
        histfunc='sum',
        range_x=(1, 10),
        labels={'rating': 'Rating value', 'cnt': 'count'},
        title='Histogram of ratings',
    )

    # Update traces to specify the bin settings
    fig.update_traces(
        xbins=dict(
            start=1,  # Start at the lowest rating
            end=10,  # End at the highest rating
            size=1,  # Bin size of 1 to align with integer values
        )
    )

    return fig


def get_reviews_count_per_player():
    """Get reviews count per player histogram."""
    reviews_cnts = Player.objects.filter(reviews_cnt__gte=3, reviews_cnt__lte=100).values_list(
        'reviews_cnt', flat=True
    )
    cntr = Counter(reviews_cnts)
    df = pd.DataFrame(cntr.items())
    fig = px.histogram(
        x=df[0],
        y=df[1],
        nbins=100,
        labels={'x': 'number of reviews', 'y': 'players'},
        title='Number of players with number of reviews',
    )
    # fig.update_yaxes(tick0=1, dtick=1)
    return fig
