"""Second-hand market health for pre-owned board games, as four charts.

A pre-owned listing is one copy, so its stock flips mean more than a new game's
do: coming into stock is a copy put on offer, and going out of stock is a copy
sold. Every chart here is read off those flips in the price history.
"""

import logging

import pandas as pd
from django.core.cache import cache
from django.db.models import Min
from plotly.graph_objs import Figure

from main.constants import CATEGORY_BOARD_GAME
from main.graphs import SHEET_INK, SHEET_MUTED, SHEET_TEAL, SHOP_LINES, sheet_layout
from main.models import Price
from main.selectors import get_today

logger = logging.getLogger(__name__)

MONTHS = 24
# A month with fewer sales than this prints no median rather than a noisy one.
MIN_SAMPLE = 5
CHART_HEIGHT = 320
PAPER = '#f3ecd9'
TEAL_WASH = 'rgba(32, 97, 91, 0.16)'


def _load_used_events() -> pd.DataFrame:
    """Load every pre-owned board game price row, marked with its stock flips.

    `listed` and `sold` are the flips that move stock. `fresh` and `sale` are
    the ones that are market activity: a copy first put on offer, and a copy
    that went for good. The difference is what the scrapes cannot see:
    - a copy already on a shop's first ever scrape was put on offer before we
      were watching, so it is stock but not a fresh listing;
    - a copy that comes back into stock was never sold, its page just went
      missing for a scrape or two;
    - a copy that goes out and reappears at the same shop under the same name
      within a day was moved to a new page, not sold and relisted.
    A copy that was not freshly listed has no known time to sell.
    """
    rows = (
        Price.objects.filter(listing__is_new=False, listing__category=CATEGORY_BOARD_GAME)
        .order_by('listing_id', 'day_id')
        .values_list(
            'listing_id',
            'listing__shop__name',
            'listing__name',
            'listing__game_id',
            'day_id',
            'in_stock',
            'price',
        )
    )
    df = pd.DataFrame(
        list(rows), columns=['listing_id', 'shop', 'name', 'game_id', 'day', 'in_stock', 'price']
    )
    logger.info(f'📈 Loaded pre-owned price rows: rows={len(df)}')
    if df.empty:
        logger.info('📈 No pre-owned board game price rows to chart')
        return df

    shop_first_day = dict(
        Price.objects.values_list('listing__shop__name').annotate(first=Min('day_id'))
    )
    df['day'] = pd.to_datetime(df['day'])
    df['price'] = df['price'].astype(float)
    df['in_stock'] = df['in_stock'].astype(bool)
    by_listing = df['listing_id']
    was_in_stock = df.groupby(by_listing)['in_stock'].shift(fill_value=False).astype(bool)
    listed = df['in_stock'] & ~was_in_stock
    sold = ~df['in_stock'] & was_in_stock

    # A listing is one copy: on offer from its first flip in, gone at its last
    # flip out, and whatever flips between were missed scrapes.
    flip_no = (listed | sold).astype(int).groupby(by_listing).cumsum()
    df['listed'] = listed & (flip_no == 1)
    df['sold'] = sold & (flip_no == flip_no.groupby(by_listing).transform('max'))

    # Pair each copy that went out with one that came in at the same shop,
    # under the same name, the same day or the next.
    outs = df.loc[df['sold'], ['shop', 'name', 'day']].reset_index(names='out_row')
    ins = df.loc[df['listed'], ['shop', 'name', 'day']].reset_index(names='in_row')
    pairs = outs.merge(ins, on=['shop', 'name'], suffixes=('_out', '_in'))
    pairs = pairs[(pairs['day_in'] - pairs['day_out']).dt.days.between(0, 1)]
    moved = df.index.isin(pairs['out_row']) | df.index.isin(pairs['in_row'])

    backlog = df['listed'] & (df['day'] == pd.to_datetime(df['shop'].map(shop_first_day)))
    df['fresh'] = df['listed'] & ~backlog & ~moved
    df['sale'] = df['sold'] & ~moved
    listed_on = df['day'].where(df['fresh']).groupby(by_listing).transform('first')
    df['held_days'] = (df['day'] - listed_on).dt.days.where(df['sale'])
    df['month'] = df['day'].dt.to_period('M').dt.to_timestamp()
    logger.info(
        f'📈 Marked pre-owned stock flips: listings={by_listing.nunique()}, '
        f'relists_bridged={int(listed.sum() - df["listed"].sum())}, '
        f'moved={int(moved.sum())}, backlog={int(backlog.sum())}, '
        f'fresh={int(df["fresh"].sum())}, sales={int(df["sale"].sum())}'
    )
    return df


def _new_price_reference(listed: pd.DataFrame) -> pd.Series:
    """Cheapest new in-stock price each game had on the day a used copy was listed.

    Game.shop_mean is not used: it is averaged over used listings too, so
    measuring used prices against it would be partly measuring them against
    themselves.
    """
    rows = Price.objects.filter(
        listing__is_new=True, listing__game_id__in=set(listed['game_id'])
    ).values_list('listing_id', 'listing__game_id', 'day_id', 'in_stock', 'price')
    new = pd.DataFrame(
        list(rows), columns=['new_listing_id', 'game_id', 'day', 'new_in_stock', 'new_price']
    )
    logger.info(f'📈 Loaded new price rows for reference: rows={len(new)}')
    if new.empty:
        logger.info('📈 No new prices to measure pre-owned prices against')
        return pd.Series(dtype=float)
    new['day'] = pd.to_datetime(new['day'])
    new['new_price'] = new['new_price'].astype(float)

    # Pair each listed used copy with every new listing of its game, then read
    # each new listing's last known state on or before the day it was listed.
    pairs = (
        listed[['game_id', 'day']]
        .reset_index(names='row')
        .merge(new[['new_listing_id', 'game_id']].drop_duplicates(), on='game_id')
        .sort_values('day')
    )
    quotes = pd.merge_asof(
        pairs,
        new.drop(columns='game_id').sort_values('day'),
        on='day',
        by='new_listing_id',
        direction='backward',
    )
    quotes = quotes[quotes['new_in_stock'].eq(True) & (quotes['new_price'] > 0)]
    reference = quotes.groupby('row')['new_price'].min()
    logger.info(
        f'📈 Matched new price references: listed={len(listed)}, with_reference={len(reference)}'
    )
    return reference


def _month_axis(fig: Figure) -> None:
    """Print a monthly x axis and a count y axis in place of the price axis."""
    fig.update_xaxes(tickformat='%b %y', hoverformat='%b %Y')
    fig.update_yaxes(tickprefix='', tickformat=',d', rangemode='tozero')


def _last(series: pd.Series):
    """The last month's value, or None when that month has none."""
    if series.empty or pd.isna(series.iloc[-1]):
        return None
    return series.iloc[-1]


def _supply_chart(df: pd.DataFrame, months: pd.DatetimeIndex) -> dict:
    """Copies listed against copies sold, per month."""
    listed = df[df['fresh']].groupby('month').size().reindex(months, fill_value=0)
    sold = df[df['sale']].groupby('month').size().reindex(months, fill_value=0)

    fig = Figure()
    for name, series, color in (('Listed', listed, SHEET_INK), ('Sold', sold, SHEET_TEAL)):
        fig.add_bar(
            x=months,
            y=series,
            name=name,
            marker=dict(color=color, line=dict(width=0)),
            hovertemplate=f'{name}  %{{y:,d}}<extra></extra>',
        )
    sheet_layout(fig, height=CHART_HEIGHT, legend=True)
    fig.update_layout(barmode='group', bargap=0.3, bargroupgap=0.08)
    _month_axis(fig)

    reading = f'{months[-1]:%b %Y}: {listed.iloc[-1]:,} listed, {sold.iloc[-1]:,} sold'
    logger.info(
        f'📈 Built supply chart: months={len(months)}, listed={int(listed.sum())}, '
        f'sold={int(sold.sum())}'
    )
    return {
        'title': 'Listed vs sold',
        'note': 'Pre-owned copies put on offer and sold each month. More sold than listed '
        'means the market is tightening.',
        'reading': reading,
        'figure': fig,
    }


def _days_to_sell_chart(df: pd.DataFrame, months: pd.DatetimeIndex) -> dict:
    """Median days a copy was on offer before it sold, per month of sale."""
    held = df.dropna(subset=['held_days']).groupby('month')['held_days']
    stats = pd.DataFrame(
        {
            'median': held.median(),
            'low': held.quantile(0.25),
            'high': held.quantile(0.75),
            'count': held.size(),
        }
    ).reindex(months)
    stats.loc[stats['count'].fillna(0) < MIN_SAMPLE, ['median', 'low', 'high']] = None

    fig = Figure()
    # The middle half of sales: an upper edge, then a lower edge filled up to it.
    fig.add_scatter(x=months, y=stats['high'], mode='lines', line=dict(width=0), hoverinfo='skip')
    fig.add_scatter(
        x=months,
        y=stats['low'],
        mode='lines',
        line=dict(width=0),
        fill='tonexty',
        fillcolor=TEAL_WASH,
        hoverinfo='skip',
    )
    fig.add_scatter(
        x=months,
        y=stats['median'],
        mode='lines+markers',
        name='Median',
        line=dict(color=SHEET_TEAL, width=2),
        marker=dict(size=6, color=SHEET_TEAL, line=dict(width=2, color=PAPER)),
        customdata=stats[['low', 'high', 'count']].to_numpy(),
        hovertemplate=(
            'Median  %{y:,.0f} days<br>Middle half  %{customdata[0]:,.0f}–'
            '%{customdata[1]:,.0f} days<br>Sales  %{customdata[2]:,.0f}<extra></extra>'
        ),
    )
    sheet_layout(fig, height=CHART_HEIGHT)
    _month_axis(fig)
    fig.update_yaxes(ticksuffix='d')

    median = _last(stats['median'])
    reading = f'{months[-1]:%b %Y}: {median:,.0f} days' if median is not None else None
    logger.info(
        f'📈 Built days-to-sell chart: months={len(months)}, '
        f'sales_timed={int(stats["count"].sum())}, last_median={median}'
    )
    return {
        'title': 'Days to sell',
        'note': 'How long a copy was on offer before it sold, by month of sale. The band '
        'holds the middle half of sales.',
        'reading': reading,
        'figure': fig,
    }


def _stock_chart(df: pd.DataFrame, start: pd.Timestamp, today: pd.Timestamp) -> dict:
    """Pre-owned copies on offer each day, stacked by shop."""
    flips = df['listed'].astype(int) - df['sold'].astype(int)
    days = pd.date_range(df['day'].min(), today)
    stock = (
        flips.groupby([df['day'], df['shop']])
        .sum()
        .unstack(fill_value=0)
        .reindex(days, fill_value=0)
        .cumsum()
    )
    stock = stock[stock.index >= start]
    # A shop keeps its ink whatever the others do, so it is set by name, not by size.
    colors = {shop: SHOP_LINES[i % len(SHOP_LINES)] for i, shop in enumerate(sorted(stock))}
    shops = [shop for shop in stock if stock[shop].max() > 0]

    fig = Figure()
    for shop in shops:
        fig.add_scatter(
            x=stock.index,
            y=stock[shop],
            mode='lines',
            name=shop,
            stackgroup='stock',
            fillcolor=colors[shop],
            line=dict(color=PAPER, width=1),
            hovertemplate=f'{shop}  %{{y:,d}}<extra></extra>',
        )
    sheet_layout(fig, height=CHART_HEIGHT, legend=True)
    fig.update_xaxes(tickformat='%b %y', hoverformat='%d %b %Y')
    fig.update_yaxes(tickprefix='', tickformat=',d', rangemode='tozero')

    on_offer = int(stock[shops].iloc[-1].sum()) if shops else 0
    logger.info(f'📈 Built stock chart: days={len(stock)}, shops={len(shops)}, on_offer={on_offer}')
    return {
        'title': 'Copies on offer',
        'note': 'Pre-owned copies in stock each day, stacked by shop.',
        'reading': f'{on_offer:,} today',
        'figure': fig,
    }


def _price_chart(df: pd.DataFrame, months: pd.DatetimeIndex) -> dict:
    """Median asking price of a used copy as a share of the cheapest new copy."""
    listed = df[df['fresh'] & df['game_id'].notna() & (df['price'] > 0)]
    listed = listed.assign(game_id=listed['game_id'].astype(int))
    reference = _new_price_reference(listed)
    ratio = (listed['price'] / reference).dropna()
    by_month = ratio.groupby(listed['month']).agg(['median', 'size']).reindex(months)
    by_month.loc[by_month['size'].fillna(0) < MIN_SAMPLE, 'median'] = None

    fig = Figure()
    fig.add_hline(
        y=1,
        line=dict(color=SHEET_INK, width=1, dash='dot'),
        annotation=dict(
            text='New price', font=dict(size=11, color=SHEET_MUTED), xanchor='left', x=0
        ),
        annotation_position='top left',
    )
    fig.add_scatter(
        x=months,
        y=by_month['median'],
        mode='lines+markers',
        name='Median',
        line=dict(color=SHEET_TEAL, width=2),
        marker=dict(size=6, color=SHEET_TEAL, line=dict(width=2, color=PAPER)),
        customdata=by_month[['size']].to_numpy(),
        hovertemplate='Median  %{y:.0%} of new<br>Copies  %{customdata[0]:,.0f}<extra></extra>',
    )
    sheet_layout(fig, height=CHART_HEIGHT)
    _month_axis(fig)
    # A share of new reads against the new price line, not against zero.
    medians = by_month['median'].dropna()
    low = min(0.5, medians.min() - 0.1) if len(medians) else 0
    top = max(1.1, medians.max() + 0.1) if len(medians) else 1.1
    fig.update_yaxes(tickformat='.0%', range=[max(low, 0), top])

    median = _last(by_month['median'])
    reading = f'{months[-1]:%b %Y}: {median:.0%} of new' if median is not None else None
    logger.info(
        f'📈 Built price chart: listed={len(listed)}, priced_against_new={len(ratio)}, '
        f'last_median={median}'
    )
    return {
        'title': 'Price against new',
        'note': 'Median asking price of a pre-owned copy, as a share of the cheapest new '
        'copy in stock that day. Only games also sold new are counted.',
        'reading': reading,
        'figure': fig,
    }


def get_second_hand_market() -> list[dict] | None:
    """Build the second-hand market charts over the last 24 full months."""
    cache_key = 'get_second_hand_market'
    if charts := cache.get(cache_key):
        logger.info(f'📈 Second-hand market charts served from cache: charts={len(charts)}')
        return charts

    logger.info(f'📈 Building second-hand market charts: months={MONTHS}')
    df = _load_used_events()
    if df.empty:
        logger.warning('📈 No second-hand market charts: no pre-owned board game prices')
        return None

    # Whole months only: the month in progress would always read as a slump.
    today = pd.Timestamp(get_today().day)
    end = today.to_period('M').to_timestamp()
    start = end - pd.DateOffset(months=MONTHS)
    months = pd.date_range(start, end, freq='MS', inclusive='left')

    charts = [
        _supply_chart(df, months),
        _days_to_sell_chart(df, months),
        _price_chart(df, months),
        _stock_chart(df, start, today),
    ]
    cache.set(cache_key, charts, timeout=43200)
    logger.info(
        f'📈 Built second-hand market charts: charts={len(charts)}, '
        f'window={start:%Y-%m}..{months[-1]:%Y-%m}'
    )
    return charts
