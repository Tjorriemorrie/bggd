import logging
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone
from plotly.graph_objs import Figure, Scatter

from main.models import Game, Listing, Shop, VisitorLog
from main.selectors import get_today

logger = logging.getLogger(__name__)


def get_game_prices_graph(game: Game):
    """Get game prices graph for every shop."""
    logger.info(f'Getting price graph for {game}')
    cache_key = f'get_game_prices_graph_{game.id}'
    if fig := cache.get(cache_key):
        return fig

    dfs = {}
    shop_names = {}  # To map slugs to shop names

    for ix, listing in enumerate(game.listings.all()):
        shop_name = listing.shop.name
        slug = f'{listing.shop.slug}_{ix}'
        shop_names[slug] = shop_name

        values = listing.prices.values_list('day__day', 'price', 'in_stock')
        if not values:
            continue

        df = pd.DataFrame(values, columns=['day', f'{slug}_price', f'{slug}_in_stock'])
        df['day'] = pd.to_datetime(df['day'])
        df = df.set_index('day')
        dfs[slug] = df

    # No graph if no dataframes are created
    if not dfs:
        return

    # Merge all dataframes from shops into one dataframe
    df = None
    for df_shop in dfs.values():
        if df is None:
            df = df_shop
        else:
            df = pd.merge(df, df_shop, how='outer', left_index=True, right_index=True)

    # Create a date range for the graph
    today = get_today()
    date_range = pd.date_range(
        df.index[0], datetime(today.day.year, today.day.month, today.day.day)
    )
    df = df.reindex(date_range)

    # Set prices to NaN where out of stock and drop stock columns
    for slug in dfs:
        df[f'{slug}_price'] = df[f'{slug}_price'].ffill()
        df[f'{slug}_in_stock'] = df[f'{slug}_in_stock'].ffill().astype(bool)

        # Set price to NaN where in_stock is False
        df.loc[~df[f'{slug}_in_stock'], f'{slug}_price'] = np.nan

    # Calculate the lowest price per day
    price_columns = [col for col in df.columns if col.endswith('_price')]
    df['lowest_price'] = df[price_columns].min(axis=1, skipna=True)

    # Calculate the rolling average of the lowest prices
    df['average_lowest_price'] = df['lowest_price'].rolling(window=365, min_periods=1).mean()

    # Create the graph
    fig = Figure()

    # Add shop-specific price lines
    for slug in dfs:
        shop_name = shop_names[slug]
        fig.add_scatter(
            x=df.index,
            y=df[f'{slug}_price'],
            mode='lines',
            name=shop_name,  # Legend will display shop name
            hovertemplate=(
                f'<b>Shop:</b> {shop_name}<br>'
                '<b>Date:</b> %{x}<br>'
                '<b>Price:</b> %{y}<extra></extra>'
            ),
        )

    # Add the average lowest price line
    fig.add_scatter(
        x=df.index,
        y=df['average_lowest_price'],
        mode='lines',
        name='Average',
        line=dict(color='blue', dash='dash'),
        hovertemplate=(
            '<b>Average</b><br>' '<b>Date:</b> %{x}<br>' '<b>Price:</b> %{y}<extra></extra>'
        ),
    )

    # Update the layout of the graph
    fig.update_layout(
        title='Prices from Shops',
        xaxis_title='Date',
        yaxis_title='Price',
        legend_title='Shop Name',
        height=700,
    )

    cache.set(cache_key, fig, timeout=43200)
    return fig


# def get_shop_sizes():
#     """Get shop sizes graph."""
#     df_data = []
#     for shop_name in SHOP_NAMES:
#         shop = Shop.objects.get(name=shop_name)
#         qs = ShopGame.objects.filter(shop=shop).filter(
#             mia=False, url__isnull=False, current_available=True
#         )
#         df_data.append({'shop': shop_name, 'in stock': qs.count()})
#     df = pd.DataFrame(df_data)
#     fig_shop_size = px.bar(df, x='shop', y='in stock', title='Shop size', height=600)
#     return fig_shop_size
#
#
# def get_shop_comparison():
#     """Get shop prices comparison."""
#     data = {}
#     combs = list(combinations(SHOP_NAMES, 2))
#     for name1, name2 in combs:
#         if name1 not in data:
#             data[name1] = {}
#         if name2 not in data:
#             data[name2] = {}
#
#         shopgames_1 = ShopGame.objects.filter(shop__name=name1, current_available=True)
#         .values_list(
#             'game', flat=True
#         )
#         shopgames_2 = ShopGame.objects.filter(shop__name=name2, current_available=True)
#         .values_list(
#             'game', flat=True
#         )
#         game_ids = set(shopgames_1) & set(shopgames_2)
#         logger.info(f'Found {len(game_ids)} between {name1} and {name2}')
#
#         if not game_ids:
#             data[name1][name2] = 0
#             data[name2][name1] = 0
#             continue
#
#         shop_1_diffs = []
#         shop_2_diffs = []
#         for game_id in game_ids:
#             shopgame_1 = ShopGame.objects.get(shop__name=name1, game__id=game_id)
#             shopgame_2 = ShopGame.objects.get(shop__name=name2, game__id=game_id)
#             shop_1_diffs.append(shopgame_2.current_price - shopgame_1.current_price)
#             shop_2_diffs.append(shopgame_1.current_price - shopgame_2.current_price)
#         data[name1][name2] = mean(shop_1_diffs)
#         data[name2][name1] = mean(shop_2_diffs)
#
#     formatted = {}
#     for name in SHOP_NAMES:
#         formatted[name] = [data[name].get(s, 0) for s in SHOP_NAMES]
#         formatted[name].append(median(formatted[name]))
#
#     sorted_formatted = dict(sorted(formatted.items(), key=lambda item: item[1][-1], reverse=True))
#
#     return sorted_formatted
#
#
# def get_reviews_daily_count_graph():
#     """Get reviews of daily count in graph."""
#     days = Day.objects.order_by('-day').all()[:90]
#     data_day = [{'Date': d.day, 'Ratings': d.reviews_cnt} for d in days]
#     df = pd.DataFrame(data_day)
#     df['Date'] = pd.to_datetime(df['Date'])
#     fig = px.bar(
#         df,
#         x='Date',
#         y='Ratings',
#         labels={'Ratings': '# of ratings'},
#         title='Ratings past quarter',
#     )
#     return fig
#
#
# def get_reviews_histogram_ratings():
#     """Get reviews histogram ratings."""
#     histogram = Review.objects.values('rating').annotate(cnt=Count('rating'))
#     df = pd.DataFrame(list(histogram))
#     fig = px.histogram(
#         df,
#         x='rating',
#         y='cnt',
#         histfunc='sum',
#         range_x=(1, 10),
#         labels={'rating': 'Rating value', 'cnt': 'count'},
#         title='Histogram of ratings',
#     )
#
#     # Update traces to specify the bin settings
#     fig.update_traces(
#         xbins=dict(
#             start=1,  # Start at the lowest rating
#             end=10,  # End at the highest rating
#             size=1,  # Bin size of 1 to align with integer values
#         )
#     )
#
#     return fig
#
#
# def get_reviews_count_per_player():
#     """Get reviews count per player histogram."""
#     reviews_cnts = Player.objects.filter(reviews_cnt__gte=3, reviews_cnt__lte=100).values_list(
#         'reviews_cnt', flat=True
#     )
#     cntr = Counter(reviews_cnts)
#     df = pd.DataFrame(cntr.items())
#     fig = px.histogram(
#         x=df[0],
#         y=df[1],
#         nbins=100,
#         labels={'x': 'number of reviews', 'y': 'players'},
#         title='Number of players with number of reviews',
#     )
#     # fig.update_yaxes(tick0=1, dtick=1)
#     return fig


def shop_price_index_graph(shop: Shop) -> Figure:
    """Price index plot by shop."""
    cache_key = f'shop_price_index_graph_{shop.id}'
    if fig := cache.get(cache_key):
        return fig

    # Use defaultdict to collect daily deltas
    daily_deltas = defaultdict(list)

    # Top 500 listings by number of price records and currently in stock
    sampled_listings = (
        Listing.objects.filter(shop=shop)
        .filter(prices__in_stock=True)
        .annotate(num_prices=Count('prices'))
        .order_by('-num_prices')[:500]
        .prefetch_related('prices')
    )

    for listing in sampled_listings:
        prices = sorted(listing.prices.all(), key=lambda p: p.day.day)

        # Initialize price history
        previous_price = None
        total_deltas = Decimal(0)

        for price_obj in prices:
            # in stock
            if price_obj.in_stock:
                # price change detected
                if previous_price:
                    delta = price_obj.price - previous_price
                    total_deltas += delta
                    daily_deltas[price_obj.day.day].append(delta)
                    previous_price = price_obj.price
                # first price
                else:
                    # add as base
                    daily_deltas[price_obj.day.day].append(Decimal(0))
                    previous_price = price_obj.price
            # out of stock
            else:
                daily_deltas[price_obj.day.day].append(-total_deltas)
                total_deltas = Decimal(0)

    # Sum deltas for each day
    delta_series = {
        day: sum(values)
        for day, values in sorted(daily_deltas.items())  # sorted ensures chronological order
    }

    # Build cumulative index from deltas
    index = []
    total = Decimal(0)
    for day, delta in delta_series.items():
        total += delta
        index.append({'date': day, 'index': float(total)})

    df = pd.DataFrame(index)

    fig = Figure()

    if not df.empty:
        fig.add_trace(
            Scatter(
                x=df['date'],
                y=df['index'],
                mode='lines+markers',
                name='Price Index',
                line=dict(color='seagreen'),
                marker=dict(size=6),
            )
        )

        fig.update_layout(
            title=f'Price Index for {shop.name}',
            xaxis_title='Date',
            yaxis_title='Cumulative Price Movement',
            template='plotly_white',
            height=700,
        )
    else:
        fig.update_layout(
            title='No price data available',
            template='plotly_white',
            height=400,
        )

    cache.set(cache_key, fig, timeout=43200)
    return fig


def get_top_paths_chart():
    """Returns a Plotly Figure for top 30 most visited paths in the last 30 days."""
    thirty_days_ago = timezone.now().date() - timedelta(days=30)

    qs = VisitorLog.objects.filter(timestamp__date__gte=thirty_days_ago).values('path')
    df = pd.DataFrame.from_records(qs)

    if df.empty:
        return None

    path_counts = df['path'].value_counts().head(30).reset_index()
    path_counts.columns = ['path', 'count']

    fig = px.bar(
        path_counts,
        x='count',
        y='path',
        orientation='h',
        title='Top 30 Visited Paths (Last 30 Days)',
        labels={'path': 'URL Path', 'count': 'Visits'},
        height=800,
    )

    fig.update_layout(
        yaxis=dict(autorange='reversed'),  # Highest at the top
        margin=dict(l=200, r=50, t=50, b=50),
    )

    return fig


def get_pageviews_per_day_chart():
    """Returns a Plotly Figure showing total pageviews per day with an average line."""
    thirty_days_ago = timezone.now().date() - timedelta(days=30)

    qs = VisitorLog.objects.filter(timestamp__date__gte=thirty_days_ago).values('timestamp')
    df = pd.DataFrame.from_records(qs)

    if df.empty:
        return None

    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    pageviews = df.groupby('date').size().reset_index(name='pageviews')

    # Calculate average
    average = pageviews['pageviews'].mean()

    fig = go.Figure()

    # Line for pageviews
    fig.add_trace(
        go.Scatter(
            x=pageviews['date'],
            y=pageviews['pageviews'],
            mode='lines+markers',
            name='Pageviews',
            line=dict(color='royalblue'),
        )
    )

    # Horizontal average line
    fig.add_trace(
        go.Scatter(
            x=pageviews['date'],
            y=[average] * len(pageviews),
            mode='lines',
            name='Average',
            line=dict(color='orange', dash='dash'),
        )
    )

    fig.update_layout(
        title='Daily Pageviews (Last 30 Days)',
        xaxis_title='Date',
        yaxis_title='Pageviews',
        xaxis=dict(tickformat='%b %d'),
        hovermode='x unified',
    )

    return fig


def get_daily_unique_ips_chart():
    """Returns a Plotly Figure of unique IPs per day for the last 30 days."""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    qs = VisitorLog.objects.filter(timestamp__gte=thirty_days_ago).values('ip_address', 'timestamp')
    df = pd.DataFrame.from_records(qs)

    if df.empty:
        return None

    # Convert timestamp to just the date
    df['date'] = pd.to_datetime(df['timestamp']).dt.date

    # Count unique IPs per day
    daily_counts = df.groupby('date')['ip_address'].nunique().reset_index()
    daily_counts.columns = ['date', 'unique_ips']

    avg_value = daily_counts['unique_ips'].mean()

    # Create bar chart
    fig = px.bar(
        daily_counts,
        x='date',
        y='unique_ips',
        title='Unique IPs per Day (Last 30 Days)',
        labels={'date': 'Date', 'unique_ips': 'Unique IPs'},
    )

    # Add average line
    fig.add_scatter(
        x=daily_counts['date'],
        y=[avg_value] * len(daily_counts),
        mode='lines',
        name='Average',
        line=dict(dash='dash', color='red'),
    )

    fig.update_layout(
        autosize=True,
        height=400,
        margin=dict(l=40, r=20, t=50, b=40),
    )

    return fig


def get_ip_request_chart():
    """Returns a Plotly Figure for total requests by IP."""
    cnt = 30
    qs = VisitorLog.objects.values('ip_address', 'user_agent')
    df = pd.DataFrame.from_records(qs)

    if df.empty:
        return None

    # Count number of requests per IP
    ip_counts = df['ip_address'].value_counts().reset_index()
    ip_counts.columns = ['ip_address', 'count']

    # Add most common user agent per IP
    most_common_agents = (
        df.groupby('ip_address')['user_agent']
        .agg(lambda x: x.value_counts().idxmax())
        .reset_index()
    )

    # Merge counts and agents
    ip_data = pd.merge(ip_counts, most_common_agents, on='ip_address')

    # Limit to top 20
    ip_data = ip_data.head(cnt)

    fig = px.bar(
        ip_data,
        x='ip_address',
        y='count',
        title=f'Top {cnt} IPs by Request Count',
        labels={'ip_address': 'IP Address', 'count': 'Requests'},
        hover_data={'user_agent': True},
    )

    fig.update_layout(
        autosize=True,
        height=400,
        margin=dict(l=40, r=20, t=50, b=40),
    )

    return fig
