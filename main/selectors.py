import logging
import multiprocessing
import re
from datetime import datetime, time, timedelta
from itertools import chain

from django.db import connection, transaction
from django.db.models import Count, ExpressionWrapper, F, FloatField, Func, Q, QuerySet, Value
from django.db.models.functions import Coalesce, Now
from django.http import HttpRequest
from django.utils import timezone
from django.utils.text import slugify
from unidecode import unidecode

from main.constants import CATEGORY_BUNDLE
from main.models import Day, Game, Listing, Scrapelog, Shop, VisitorLog

logger = logging.getLogger(__name__)


class UnixTimestamp(Func):
    function = 'strftime'
    template = "%(function)s('%%%%s', %(expressions)s)"  # Escape % with %%
    output_field = FloatField()  # Explicitly declare the output as FloatField


def get_client_ip(request: HttpRequest):
    """Retrieve the client IP address from the request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
    return ip


def get_today() -> Day:
    """Get today as model instance."""
    today = timezone.now()
    day, _ = Day.objects.get_or_create(
        day=datetime(today.year, today.month, today.day),
        defaults={
            # 'reviews_cnt': 0,
            # 'reviews_avg': 0,
            # 'last_review_id': 0,
            # 'last_review_at': now(),
        },
    )
    return day


def get_day_at(date_val) -> Day:
    """Get specific day from string."""
    day, day_created = Day.objects.get_or_create(
        day=date_val,
        defaults={
            # 'reviews_cnt': 0,
            # 'reviews_avg': 0,
            # 'last_review_id': 0,
            # 'last_review_at': now(),
        },
    )
    if day_created:
        logger.info(f'Created day! {day}')
    return day


# Create a process-safe lock
shop_lock = multiprocessing.Lock()


def upsert_shop(shop_name: str) -> Shop:
    """Get shop by name."""
    with shop_lock, transaction.atomic():
        shop, created = Shop.objects.get_or_create(
            name=shop_name,
            defaults={
                'slug': slugify(unidecode(shop_name)),
            },
        )
        if created:
            logger.info(f'Created shop {shop}')
        return shop


def get_latest_new_games() -> QuerySet[Game]:
    """Get latest new games."""
    games = Game.objects.order_by('-created_at').all()[:12]
    return games


def get_best_savings_games(reverse: bool = False) -> QuerySet[Game]:
    """Get the best savings games."""
    games = Game.objects.order_by(f'{"" if reverse else "-"}shop_saving', '-shop_price').all()[:24]
    return games


def list_listings_without_games() -> QuerySet[Listing]:
    """Gives listings without bgg_ids."""
    # first get any unlooked that is missing
    listings = Listing.objects.filter(bgg_looked_at__isnull=True, bgg_missing=True).order_by(
        '-price'
    )
    if listings:
        return listings

    # make sure home page is all correct
    savings = get_best_savings_games()
    worst = get_best_savings_games(reverse=True)
    latest = list_newest_games()
    home_page_game_ids = [g.id for g in chain(savings, latest, worst)]
    listings = Listing.objects.filter(
        bgg_looked_at__isnull=True, game_id__in=home_page_game_ids
    ).order_by('-price')
    if listings:
        return listings

    # else sort it by discount
    listings = Listing.objects.filter(
        bgg_looked_at__isnull=True, game__isnull=False, game__shop_saving__gt=0
    ).order_by('-game__shop_saving')
    if listings:
        return listings

    # recently created listings
    days_ago = timezone.now() - timedelta(days=7)
    listings = Listing.objects.filter(bgg_looked_at__isnull=True, created_at__gt=days_ago).order_by(
        '-price'
    )
    if listings:
        return listings

    # lastly just by updated date
    listings = Listing.objects.filter(bgg_looked_at__isnull=True).order_by('-in_stock', '-price')
    if listings:
        return listings

    # otherwise just rotate from oldest
    listings = (
        Listing.objects.annotate(
            bgg_looked_at_timestamp=Coalesce(
                UnixTimestamp(F('bgg_looked_at')), Value(0.0, output_field=FloatField())
            ),
            priced_at_timestamp=Coalesce(
                UnixTimestamp(F('priced_at')), Value(0.0, output_field=FloatField())
            ),
            now_timestamp=UnixTimestamp(Now()),
        )
        .annotate(
            diff_fields=ExpressionWrapper(
                (F('priced_at_timestamp') - F('bgg_looked_at_timestamp')),
                output_field=FloatField(),
            )
        )
        .order_by('-diff_fields')
    )

    return listings


def list_listings_rated_today() -> QuerySet[Listing]:
    """Gives listings without bgg_ids."""
    start_of_day = datetime.combine(timezone.now().date(), time.min, tzinfo=timezone.now().tzinfo)
    listings = Listing.objects.filter(bgg_looked_at__gte=start_of_day).order_by('bgg_looked_at')
    return listings


def best_listing_by_game(game: Game) -> Listing | None:
    """Returns best listing with available stock."""
    return game.listings.filter(in_stock=True, price__isnull=False).order_by('price').first()


def get_last_scrape(shop: Shop) -> Scrapelog | None:
    """Last scrape of shop."""
    scrapelog = Scrapelog.objects.filter(target=f'shop {shop.name}').order_by('scraped_at').last()
    return scrapelog


def list_newest_games():
    """List newest games."""
    max_num = 18
    rank_cutoff = 3_000
    days_to_fix = 1
    days_ago = timezone.now() - timedelta(days=days_to_fix)
    games = (
        Game.objects.filter(created_at__lt=days_ago, shop_in_stock=True, rank__lte=rank_cutoff)
        .order_by('-created_at')
        .all()[:max_num]
    )
    return games


def list_popular_games(excl_ids):
    """List popular games."""
    # Calculate the date 4 weeks ago
    four_weeks_ago = timezone.now() - timedelta(weeks=52)

    pop_games = (
        Game.objects.filter(pageviews__viewed_at__gte=four_weeks_ago)
        .exclude(id__in=excl_ids)
        .annotate(pageview_count=Count('pageviews'))
        .order_by('-pageview_count')[:6]
    )

    return pop_games


def list_bundle_listings():
    """List bundled listings."""
    bundles = Listing.objects.filter(category=CATEGORY_BUNDLE, in_stock=True).order_by(
        '-created_at'
    )
    return bundles


def list_expensive_unique_by_shop(shop: Shop) -> QuerySet[Game]:
    """Return list of most expensive unique games."""
    top_12_expensive_exclusive_games = (
        Game.objects.filter(shop_best=shop)
        .annotate(listing_shops=Count('listings__shop', distinct=True))
        .filter(listing_shops=1)
        .order_by('-shop_price')[:24]
    )
    return top_12_expensive_exclusive_games


_BOT_UA_RE = re.compile(
    r'bot|crawler|scraper|spider|wget|curl|python-requests|aiohttp|headless', re.I
)
_ADMIN_PATHS = {'xmlrpc.php', 'wp-login.php'}


def _three_octet_expr():
    """Return a Func that extracts the first three octets (SQLite)."""
    return Func(
        F('ip_address'),
        function='substr',
        template=(
            'substr(%(expressions)s, 1, '
            "length(%(expressions)s) - instr(reverse(%(expressions)s), '.') - 1)"
        ),
    )


def top_bad_bot_by_user_agent_past_week(limit: int = 7):
    """Groups by (first-three-octets, user-agent)."""
    since = timezone.now() - timedelta(days=7)

    # SQLite SQL: substr(ip_address, 1, length(ip_address) - instr(reverse(ip_address), '.') - 1)
    prefix_expr = _three_octet_expr()

    qs = (
        VisitorLog.objects.filter(timestamp__gte=since)
        .annotate(prefix=prefix_expr)
        .values('prefix', 'user_agent')  # GROUP BY both
        .annotate(requests=Count('id'))
        .order_by('-requests')
    )

    # keep only bad-bot rows
    results = [
        {'prefix': row['prefix'], 'user_agent': row['user_agent'], 'requests': row['requests']}
        for row in qs
        if _BOT_UA_RE.search(row['user_agent'] or '')
    ][:limit]

    return results


def top_bad_bot_by_admin_scanner_past_week(limit: int = 7):
    """Look for requests whose path ends with xmlrpc.php or wp-login.php."""
    since = timezone.now() - timedelta(days=7)

    # Build a single Q object that matches *either* path
    path_q = Q()
    for p in _ADMIN_PATHS:
        path_q |= Q(path__iendswith=p)

    qs = (
        VisitorLog.objects.filter(timestamp__gte=since)
        .filter(path_q)
        .annotate(prefix=_three_octet_expr())
        .annotate(
            matched_path=Func(
                F('path'),
                function='substr',
                template="substr(%(expressions)s, -instr(reverse(%(expressions)s), '/') + 1)",
            )  # extracts the final component, e.g. xmlrpc.php
        )
        .values('prefix', 'matched_path')
        .annotate(requests=Count('id'))
        .order_by('-requests')
    )

    # Convert queryset to list and slice
    return list(qs[:limit])


def top_bad_bot_by_burst_past_week(window_secs=60, limit=7):
    """Bad bots by burst of 60s."""
    since = timezone.now() - timedelta(days=7)
    since_unix = int(since.timestamp())

    sql = f"""
    SELECT
        substr(ip_address, 1, length(ip_address) - instr(reverse(ip_address), '.') - 1) AS prefix,
        CAST(strftime('%s', timestamp) / {window_secs} AS INTEGER) AS bucket,
        COUNT(*) AS cnt
    FROM main_visitorlog
    WHERE strftime('%s', timestamp) >= {since_unix}
    GROUP BY prefix, bucket
    ORDER BY cnt DESC
    """

    bursts = {}
    totals = {}

    with connection.cursor() as cursor:
        cursor.execute(sql)
        for prefix, bucket, cnt in cursor.fetchall():  # noqa: B007
            bursts[prefix] = max(bursts.get(prefix, 0), cnt)
            totals[prefix] = totals.get(prefix, 0) + cnt

    ranked = sorted(bursts.items(), key=lambda x: x[1], reverse=True)
    return [{'prefix': p, 'max_burst': b, 'total': totals[p]} for p, b in ranked[:limit]]


def top_bad_bot_by_homepage_past_week(limit=7):
    """Bad bots by not going to homepage."""
    since = timezone.now() - timedelta(days=7)

    # 1. All /24 prefixes with any request in the window
    all_qs = (
        VisitorLog.objects.filter(timestamp__gte=since)
        .annotate(prefix=_three_octet_expr())
        .values('prefix')
        .annotate(total=Count('id'))
    )

    # 2. Prefixes that *did* hit the homepage
    homepage_qs = (
        VisitorLog.objects.filter(timestamp__gte=since)
        .filter(Q(path='/') | Q(path__iexact='/index.html'))
        .annotate(prefix=_three_octet_expr())
        .values_list('prefix', flat=True)
        .distinct()
    )
    homepage_set = set(homepage_qs)

    # 3. Exclude homepage hitters
    candidates = [
        {'prefix': row['prefix'], 'total': row['total']}
        for row in all_qs
        if row['prefix'] not in homepage_set
    ]

    # 4. Fallback: if nobody qualifies, return an empty list explicitly
    candidates.sort(key=lambda x: x['total'], reverse=True)
    return candidates[:limit]
