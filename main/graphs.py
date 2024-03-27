import logging
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from main.constants import STOCK_OUT
from main.models import Day, Game

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
