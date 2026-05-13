import logging
import random
import re
from contextlib import suppress
from datetime import datetime
from time import sleep

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from django.db import OperationalError
from django.utils import timezone
from django.utils.text import slugify
from retry import retry
from unidecode import unidecode

from django.conf import settings as django_settings

import main.constants as c
from main.errors import (
    BggGameNotFoundError,
    RedirectError,
    RequestsError,
    ScrapeError,
    TooManyRequestsError,
)
from main.models import Game, Label, Listing
from main.selectors import best_listing_by_game, get_best_savings_games, get_today

logger = logging.getLogger(__name__)

# URL_LOGIN = 'https://boardgamegeek.com/login/api/v1'
# URL_CURRENT = 'https://boardgamegeek.com/api/accounts/current'
# URL_RANKINGS = r'https://www.boardgamegeek.com/browse/boardgame/page/'
# URL_HOTNESS = r'https://boardgamegeek.com/xmlapi2/hot?boardgame'
# URL_THING = r'https://boardgamegeek.com/xmlapi2/thing?id={bgg_id}'
URL_GAME = r'https://www.boardgamegeek.com/boardgame/{bgg_id}'
URL_THING = r'https://boardgamegeek.com/xmlapi2/thing'

# BGG XML <item type=...> -> internal label string
BGG_TYPE_LABELS = {
    'boardgame': 'Board Game',
    'boardgameexpansion': 'Board Game',
    'rpgitem': 'RPG Item',
}
# URL_GAME_DETAILS = r'https://api.geekdo.com/api/geekitems?nosession=1&objectid={bgg_id}&objecttype=thing&subtype=boardgame'  # noqa: E501
# URL_GAME_RATINGS = r'https://api.geekdo.com/api/collections?ajax=1&objectid={bgg_id}&objecttype=thing&oneperuser=1&rated=1&require_review=true&sort=review_tstamp&showcount=50&pageid={p}'  # noqa: E501
# URL_GAME_NUMPLAYERS = r'https://www.boardgamegeek.com/geekitempoll.php?action=view&itempolltype=numplayers&objectid={bgg_id}&objecttype=thing'  # noqa: E501
# URL_GAME_NUMPLAYERS_RESULTS = (
#     r'https://www.boardgamegeek.com/geekpoll.php?action=results&pollid={poll_id}'
# )
# URL_PLAYER_RATINGS = r'https://www.boardgamegeek.com/geekcollection.php?ajax=1&action=collectionpage&username={nick}&gallery=&sort=rating&sortdir=desc&page=&pageID={page}&ff=1&hiddencolumns=&publisherid=&searchstr=&rankobjecttype=subtype&rankobjectid=1&columns[]=title&columns[]=rating&columns[]=bggrating&columns[]=comment&minrating=&rating=&minbggrating=&bggrating=&minplays=&maxplays=&searchfield=title&geekranks=Board%20Game%20Rank&subtype=boardgame&excludesubtype=boardgameexpansion&own=both&trade=both&want=both&wanttobuy=both&prevowned=both&comment=both&wishlist=both&rated=both&played=both&wanttoplay=both&preordered=both&hasparts=both&wantparts=both&wishlistpriority='  # noqa: E501

# ruff: noqa
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
]

sleep_time = 0


@retry((TooManyRequestsError, RequestsError), delay=3, max_delay=60, tries=42)
def get(
    url: str, params: dict = None, headers: dict = None, redirect: bool = False
) -> requests.Response:
    """Helper function to do back off fetches with requests."""
    global sleep_time  # noqa PLW0603

    sleep(sleep_time)

    headers_default = {
        'User-Agent': random.choice(USER_AGENTS),  # noqa
    }
    if headers:
        headers_default.update(headers)

    try:
        res = requests.get(
            url, params=params, headers=headers_default, timeout=30, allow_redirects=redirect
        )
    except requests.RequestException as exc:
        logger.error(f'Connection error! url={url}')
        logger.error(f'Connection error! exc={exc}')
        sleep(5)
        raise RequestsError() from exc

    if res.status_code in [requests.codes.too_many, 430]:
        prev = sleep_time
        sleep_time = round(sleep_time + 0.05, 4)
        logger.error(
            f'Too many requests for {url} {params}; sleep {prev}s -> {sleep_time}s (+0.05)'
        )
        raise TooManyRequestsError()
    elif res.status_code in [401, 403]:
        prev = sleep_time
        sleep_time = round(sleep_time + 0.05, 4)
        logger.error(
            f'{res.status_code} blocked for {url} {params}; sleep {prev}s -> {sleep_time}s (+0.05)'
        )
        raise TooManyRequestsError()
    elif res.status_code >= requests.codes.server_error:
        prev = sleep_time
        sleep_time = round(sleep_time + 0.05, 4)
        logger.error(
            f'Server error ({res.status_code}) for {url}; sleep {prev}s -> {sleep_time}s (+0.05)'
        )
        raise TooManyRequestsError()
    elif requests.codes.moved <= res.status_code < requests.codes.bad_request:
        logger.error(f'Redirect required: {url}')
        raise RedirectError()

    # success: very slowly decay the throttle (100x slower than bump) so a
    # built-up buffer survives bursts of successes between rate-limits
    if sleep_time:
        sleep_time = round(max(0, sleep_time - 0.0005), 4)

    try:
        res.raise_for_status()
    except requests.RequestException as exc:
        logger.error(f'request bad status: {exc}')

    return res


def scrape_new_games():
    """Scrape games from bgg_ids from listings."""
    logger.info('Scraping new games...')

    listings = list(
        Listing.objects.filter(bgg_id__isnull=False, bgg_missing=False, game__isnull=True).all()
    )

    total = len(listings)
    logger.info(f'Found {total} listings to scrape.')

    if total == 0:
        logger.info('No new games to scrape.')
        return

    for ix, listing in enumerate(listings):
        try:
            game = Game.objects.get(id=listing.bgg_id)
            game.shop_outdated = True
            game.save()
        except Game.DoesNotExist:
            try:
                game = scrape_game(listing.bgg_id)
            except BggGameNotFoundError:
                logger.warning(f'Boardgamegeek id {listing.bgg_id} not found!')
                listing.bgg_id = None
                listing.bgg_missing = True
                listing.bgg_scraped_at = timezone.now()
                listing.save()
                return

        listing.game = game
        listing.bgg_missing = False
        listing.bgg_scraped_at = timezone.now()
        listing.save()
        logger.info(f'{ix}/{total} Successfully scraped and saved game for {listing}')


@retry((OperationalError, ScrapeError), tries=99, delay=1, jitter=1, max_delay=30)
def scrape_game(bgg_id: int) -> Game:
    """Scrape the game from boardgamegeek via XML API2."""
    logger.info(f'Scraping {bgg_id}...')
    headers = {'Authorization': f'Bearer {django_settings.BGG_AUTH}'}
    params = {'id': bgg_id, 'stats': 1}
    res = get(URL_THING, params, headers=headers)

    soup = BeautifulSoup(res.content, 'xml')
    item = soup.find('item')
    if not item:
        raise BggGameNotFoundError()

    xml_type = item.get('type')
    if xml_type not in BGG_TYPE_LABELS:
        raise NotImplementedError(f'Unknown XML item type: {xml_type}')

    # get instance
    try:
        game = Game.objects.get(id=bgg_id)
    except Game.DoesNotExist:
        game = Game()

    # info
    name_elem = item.find('name', attrs={'type': 'primary'}) or item.find('name')
    game.name = name_elem['value']
    game.slug = slugify(unidecode(game.name))
    game.label = BGG_TYPE_LABELS[xml_type]
    game.year = int(item.find('yearpublished')['value'])
    game.url = URL_GAME.format(bgg_id=bgg_id)
    rank_elem = item.find('rank', attrs={'type': 'subtype', 'id': '1'})
    if rank_elem is not None:
        with suppress(TypeError, ValueError):
            game.rank = int(rank_elem.get('value')) or None
    image_elem = item.find('image')
    if image_elem and image_elem.text:
        game.img = image_elem.text
    description_html = (item.find('description').text or '').replace('\n', ' ')
    description = BeautifulSoup(description_html, 'html.parser').text
    game.description = description.replace('  ', ' ').strip()

    if xml_type in ('boardgame', 'boardgameexpansion'):
        game = scrape_boardgame_details(bgg_id, game, item)

    game.scraped_at = timezone.now()
    game.save()
    logger.info(f'Saved game {game}')
    return game


def _parse_player_range(value: str | None) -> tuple[int, int] | None:
    """Parse poll-summary text like 'Best with 3-4 players' / 'with 2+ players'."""
    if not value:
        return None
    match = re.search(r'(\d+)(?:\s*[-–]\s*(\d+)|\s*(\+))?', value)
    if not match:
        return None
    lo = int(match.group(1))
    if match.group(2):
        return lo, int(match.group(2))
    if match.group(3):
        return lo, 8
    return lo, lo


def scrape_boardgame_details(bgg_id: int, game: Game, item) -> Game:
    """Get specific boardgame details from BGG XML <item>."""
    ratings = item.find('ratings')
    if ratings:
        avg_elem = ratings.find('average')
        if avg_elem is not None:
            with suppress(TypeError, ValueError):
                game.rating = float(avg_elem.get('value'))
        weight_elem = ratings.find('averageweight')
        if weight_elem is not None:
            with suppress(TypeError, ValueError):
                game.weight_avg = float(weight_elem.get('value'))

    game.min_players = int(item.find('minplayers')['value'])
    game.max_players = int(item.find('maxplayers')['value'])
    game.min_play_time = int(item.find('minplaytime')['value'])
    game.max_play_time = int(item.find('maxplaytime')['value'])
    game.min_age = int(item.find('minage')['value'])

    # suggested numplayers poll-summary -> recommended / best ranges
    poll_summary = item.find('poll-summary', attrs={'name': 'suggested_numplayers'})
    if poll_summary:
        rec_elem = poll_summary.find('result', attrs={'name': 'recommmendedwith'})
        best_elem = poll_summary.find('result', attrs={'name': 'bestwith'})
        rec_range = _parse_player_range(rec_elem.get('value') if rec_elem else None)
        best_range = _parse_player_range(best_elem.get('value') if best_elem else None)
        if rec_range:
            game.rec_min_players, game.rec_max_players = rec_range
        if best_range:
            game.best_min_players, game.best_max_players = best_range

    # suggested_playerage poll -> rec_min_age (highest-voted age bucket)
    age_poll = item.find('poll', attrs={'name': 'suggested_playerage'})
    if age_poll:
        results = age_poll.find('results')
        if results:
            best_result = max(
                results.find_all('result'),
                key=lambda r: int(r.get('numvotes', '0') or 0),
                default=None,
            )
            if best_result is not None and int(best_result.get('numvotes', '0') or 0) > 0:
                age_str = best_result.get('value', '').strip()
                with suppress(ValueError):
                    game.rec_min_age = int(age_str.split()[0].rstrip('+'))

    # labels (require game to be saved)
    if not game.pk:
        game.id = bgg_id
        game.save()
    game_links_labels = {
        'boardgamecategory': ('categories', c.LABEL_CATEGORY),
        'boardgamemechanic': ('mechanics', c.LABEL_MECHANIC),
        'boardgamefamily': ('families', c.LABEL_FAMILY),
        'boardgamesubdomain': ('subdomains', c.LABEL_SUBDOMAIN),
    }
    for link_type, (attr, label_type) in game_links_labels.items():
        data = []
        for link in item.find_all('link', attrs={'type': link_type}):
            label, _ = Label.objects.get_or_create(
                id=int(link['id']),
                defaults={'type': label_type, 'name': link['value']},
            )
            data.append(label)
        getattr(game, attr).set(data)

    return game


def _not_found(name: str, search_url: str = '') -> dict:
    """Return a not-found result dict."""
    return {
        'name': 'not_found',
        'bgg_id': None,
        'image': None,
        'search': search_url,
    }


def fetch_bgg_thing(bgg_id: int) -> dict | None:
    """Fetch game name and image from BGG XML API2 by bgg_id (requires BGG_AUTH)."""
    host = 'https://boardgamegeek.com/xmlapi2/thing'
    headers = {'Authorization': f'Bearer {django_settings.BGG_AUTH}'}
    params = {'id': bgg_id}

    try:
        res = get(host, params, headers=headers)
    except (TooManyRequestsError, RequestsError):
        return None

    soup = BeautifulSoup(res.content, 'xml')
    item = soup.find('item')
    if not item:
        return None

    name_elem = soup.find('name', attrs={'type': 'primary'}) or soup.find('name')
    image_elem = item.find('image')
    thumbnail_elem = item.find('thumbnail')

    image_url = None
    if image_elem and image_elem.text:
        image_url = image_elem.text
    elif thumbnail_elem and thumbnail_elem.text:
        image_url = thumbnail_elem.text

    return {
        'name': name_elem['value'] if name_elem else None,
        'bgg_id': bgg_id,
        'image': image_url,
        'search': f'https://boardgamegeek.com/boardgame/{bgg_id}',
    }


def _search_bgg_api(name: str) -> dict | None:
    """Search BGG using the XML API2 (requires BGG_AUTH)."""
    host = 'https://boardgamegeek.com/xmlapi2/search'
    headers = {'Authorization': f'Bearer {django_settings.BGG_AUTH}'}
    params = {'type': 'boardgame', 'query': name, 'exact': 1}

    res = get(host, params, headers=headers)
    soup = BeautifulSoup(res.content, 'xml')
    items = soup.find_all('item')

    if not items:
        params.pop('exact')
        res = get(host, params, headers=headers)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item')

    if not items:
        return None

    item = items[0]
    return {
        'name': item.find('name')['value'],
        'bgg_id': item['id'],
        'image': None,
        'search': res.request.url,
    }


def search_bgg(name: str) -> dict:
    """Search BGG for game by name."""
    name = re.sub(r'board game', '', str(name), flags=re.IGNORECASE).strip()
    if not name:
        return _not_found(name)

    result = _search_bgg_api(name)
    if result:
        return result

    # Retry with fewer words (trim first and last word)
    name_cut = ' '.join(name.split()[1:-1]).strip()
    if name_cut:
        return search_bgg(name_cut)
    return _not_found(name)


# def scrape_game_reviews(game: Game):
#     """Scrape game reviews from boardgamegeek."""
#     logger.info(f'Scraping reviews of {game}')
#     num_items = 0
#
#     # first run from the front
#     p = 0
#     existing = 0
#     while existing <= SCRAPE_REVIEWS_EXISTING_BUFFER:
#         p += 1
#         logger.info(f'Scraping page {p}/{num_items // 50 + 1} for reviews...')
#         res = get(URL_GAME_RATINGS.format(bgg_id=game.bgg_id, p=p)).json()
#
#         if not res['items']:
#             logger.warning(f'No more items found from page {p}!')
#             break
#
#         for item in res['items']:
#             try:
#                 review, created = parse_game_review(game, item)
#             except BadDateError:
#                 continue
#             existing += not bool(created)
#             # logger.info(f'{created and "Created" or "Updated"} {review}')
#
#         if not num_items:
#             num_items = res['config']['numitems']
#
#     # then continue at the back
#     reviews_cnt = game.reviews.count()
#     if reviews_cnt < num_items * 0.999:
#         p = reviews_cnt // 50
#         while True:
#             p += 1
#             logger.info(f'Scraping page {p}/{num_items // 50 + 1} for reviews...')
#             res = get(URL_GAME_RATINGS.format(bgg_id=game.bgg_id, p=p)).json()
#
#             if not res['items']:
#                 logger.warning(f'No more items found from page {p}!')
#                 break
#
#             for item in res['items']:
#                 try:
#                     review, created = parse_game_review(game, item)
#                 except BadDateError:
#                     continue
#                 reviews_cnt += bool(created)
#                 # logger.info(f'{created and "Created" or "Updated"} {review}')
#
#     # update rating
#     avg_rating = game.reviews.all().aggregate(Avg('rating'))
#     game.rating = avg_rating['rating__avg']
#     game.reviews_cnt = game.reviews.count()
#
#     logger.info(f'Finished scraping reviews for {game}!')
#
#
# def parse_game_review(game: Game, item: dict) -> tuple[Review, bool]:  # noqa PLR0912
#     """Parse game review from html."""
#     item['rating'] = round(float(item['rating']), 1)
#     item['rating'] = max([1.0, item['rating']])
#     item['rating'] = min([10.0, item['rating']])
#     try:
#         player, _ = Player.objects.get_or_create(
#             nick=item['user']['username'],
#             defaults={
#                 'country': item['user']['country'],
#                 'avatar': item['user'].get('avatarurl_md'),
#             },
#         )
#     except Player.MultipleObjectsReturned:
#         logger.info(f'Found multiple nicks {item["user"]["username"]}')
#         raise
#     tstamp = item['review_tstamp'] or item['tstamp']
#     reviewed_at = make_aware(datetime.strptime(tstamp, '%Y-%m-%d %H:%M:%S'))
#     twenty_years_ago = now() - timedelta(weeks=1_040)
#     if twenty_years_ago > reviewed_at > now():
#         raise BadDateError('reviewed_at')
#     try:
#         review, created = Review.objects.get_or_create(
#             bgg_id=item['collid'],
#             defaults={
#                 'game': game,
#                 'player': player,
#                 'rating': item['rating'],
#                 'reviewed_at': reviewed_at,
#             },
#         )
#     except IntegrityError:
#         logger.warning(f'Integrity error on review item {item}!')
#         review, created = Review.objects.update_or_create(
#             game=game,
#             player=player,
#             defaults={
#                 'bgg_id': item['collid'],
#                 'rating': item['rating'],
#                 'reviewed_at': reviewed_at,
#             },
#         )
#         logger.warning(f'{created and "Created" or "Updated"} review')
#     except Review.MultipleObjectsReturned:
#         logger.warning(f'Multiple objects returned for {item}!')
#         Review.objects.filter(game=game, player=player).delete()
#         return parse_game_review(game, item)
#
#     # mark player as changed only for new reviews, not changes (as below)
#     # allows changed players to pick this up
#     if created:
#         player.last_review_at = now()
#         player.is_outdated = True
#         player.save()
#         # outdate gameday
#         outdate_gameday_by_review(review)
#
#     # update existing review if different review tstamp or rating
#     if review.reviewed_at != reviewed_at or review.rating != item['rating']:
#         logger.info(f'{review} rating changed from {review.rating} to {item["rating"]}')
#         review.reviewed_at = reviewed_at
#         review.rating = item['rating']
#         created = True
#         review.save()
#
#     # review status
#     for status, _ in REVIEW_STATUS_CHOICES:
#         if status not in item['status']:
#             continue
#         if status == review.status:
#             break
#         else:
#             review.status = status
#             review.save()
#             break
#     else:
#         # if item['status'] and settings.DEBUG:
#         #     raise Exception(f'unknown statuses: {item["status"]}')
#         review.status = REVIEW_STATUS_NONE
#         review.save()
#
#     return review, created
#
#
# @retry(OperationalError, delay=3, jitter=3, max_delay=30)
# def scrape_player(player: Player):
#     """Scrape the player details."""
#     res = get(player.bgg_link)
#     html = BeautifulSoup(res.text, 'html.parser')
#     avatar_block = html.find('div', class_='avatarblock')
#     if not avatar_block:
#         raise PlayerScrapeError('user does not exist')
#     player.bgg_id = avatar_block['data-userid']
#     avatar_divs = avatar_block.find_all('div')
#     player.shop_name = avatar_divs[0].text.strip() or None
#     with suppress(TypeError):
#         player.avatar = avatar_block.find('img', alt='Avatar')['src']
#     try:
#         country, *areas = avatar_divs[2].stripped_strings
#         player.country = country
#         player.area = ', '.join(areas)
#     except ValueError:
#         pass
#     player.scraped_at = now()
#     player.save()
#
#
# def scrape_player_ratings(player: Player):  # noqa: PLR0915 PLR0912
#     """Scrape the player ratings."""
#     orphan_game_ids = list(player.reviews.values_list('game_id', flat=True))
#     page = 0
#     while True:
#         page += 1
#         url = URL_PLAYER_RATINGS.format(nick=player.nick, page=page)
#         res = get(url)
#         html = BeautifulSoup(res.text, 'html.parser')
#         table = html.find('table', id='collectionitems')
#         try:
#             rows = table.find_all('tr')
#         except Exception as exc:
#             logger.exception(f'No ratings for player URL = {url}')
#             raise PlayerRatingUsernameNotFoundError() from exc
#         if len(rows) < ROWS_TABLE_HEADERS:
#             break
#         for row in rows[1:]:
#             # bgg id
#             bgg_id = int(row['id'].split('_')[-1])
#             cells = row.find_all('td')
#             # get game
#             game_row = cells[0].find('a')['href']
#             matches = re.search(r'/boardgame/(\d+)/', game_row)
#             game_bgg_id = int(matches.group(1))
#             try:
#                 game = Game.objects.get(bgg_id=game_bgg_id)
#             except Game.DoesNotExist:
#                 unknown_game = cells[0].text.replace('\n', ' ').replace('\r', ' ')
#                 logger.debug(f'Skipping unknown game {unknown_game}')
#                 continue
#             # get rating
#             rating_info = list(cells[1].stripped_strings)
#             if rating_info[0] == 'N/A':
#                 continue
#             rating = round(float(rating_info[0]), 1)
#             rating = min(10.0, rating)
#             rating = max(1.0, rating)
#             try:
#                 rated_on = make_aware(datetime.strptime(rating_info[1].rstrip('*'), '%b %Y'))
#             except IndexError:
#                 # month and year is in next year. just skip.
#                 continue
#             # get comment
#             comment_and_date = list(cells[3].stripped_strings)
#             comment = comment_and_date[0] if comment_and_date else None
#
#             # update review
#             try:
#                 review = Review.objects.get(game=game, player=player)
#                 try:  # should always have game id if review exists
#                     orphan_game_ids.remove(review.game.id)
#                 except ValueError:
#                     logger.error(
#                         f'{review.game.id} not found in remaining game ids {orphan_game_ids}'
#                     )
#             except Review.DoesNotExist:
#                 review = Review.objects.create(
#                     player=player,
#                     game=game,
#                     bgg_id=bgg_id,
#                     rating=rating,
#                     comment=comment,
#                     reviewed_at=rated_on,
#                 )
#                 logger.info(f'Created missed {review} for existing {game}!')
#                 continue
#
#             if review.rating != rating or review.comment != comment:
#                 logger.info(
#                     f'Rating for {game} changed from {review.rating} to {rating}: {comment}'
#                 )
#                 review.rating = rating
#                 review.comment = comment
#                 review.save()
#
#     # remove orphan reviews
#     for game_id in orphan_game_ids:
#         try:
#             review = Review.objects.get(player=player, game_id=game_id)
#         except Review.DoesNotExist:
#             continue
#         logger.info(f'Deleting orphan: {review}')
#         review.delete()


def update_outdated_game_shop_prices(all_: bool):
    """Update outdated shop prices on games."""
    if all_:
        games = list(Game.objects.all())
    else:
        oldest_cutoff = Game.objects.count() // 28
        games = list(
            {
                *Game.objects.filter(shop_outdated=True).all(),
                *get_best_savings_games(),
                *Game.objects.order_by('shop_updated_at')[:oldest_cutoff],
            }
        )
    total = len(games)
    for ix, game in enumerate(games):
        logger.info(f'{ix}/{total} Updating prices for {game}')
        update_game_shop_prices(game)


def update_game_shop_prices(game: Game):  # noqa: PLR0915
    """Update the GameDay with the prices of the best shop.

    Then set the final current value on the game.
    """
    logger.info(f'updating game shop prices for {game}')
    # retrieve all shop prices
    listings_by_shop = {}
    dfs = {}
    for ix, listing in enumerate(game.listings.all()):
        slug = f'{slugify(listing.shop.name)}_{ix}'
        values = listing.prices.values_list('day__day', 'price', 'in_stock')
        if not values:
            continue
        df = pd.DataFrame(values, columns=['day', f'{slug}_price', f'{slug}_in_stock'])
        df[f'{slug}_price'] = df[f'{slug}_price'].astype(float)
        df[f'{slug}_in_stock'] = df[f'{slug}_in_stock'].astype(bool)
        df['day'] = pd.to_datetime(df['day'])
        df = df.set_index('day')
        dfs[slug] = df
        listings_by_shop[slug] = listing

    # remove game if it is not in a shop
    if not dfs:
        game.delete()
        return

    # merge all dfs from shops into one DF
    df = None
    for df_shop in dfs.values():
        if df is None:
            df = df_shop
        else:
            df = pd.merge(df, df_shop, how='outer', left_index=True, right_index=True)
    day = get_today()
    date_range = pd.date_range(df.index[0], datetime(day.day.year, day.day.month, day.day.day))
    df = df.reindex(date_range)

    # set price to Nan where out of stock, and drop stock
    for slug in dfs:
        df[f'{slug}_price'] = df[f'{slug}_price'].ffill()
        df[f'{slug}_in_stock'] = df[f'{slug}_in_stock'].ffill().astype(bool)
        # Set price to NaN where in_stock is False
        df.loc[~df[f'{slug}_in_stock'], f'{slug}_price'] = np.nan
        # Drop the in_stock column
        df.drop(f'{slug}_in_stock', axis=1, inplace=True)

    # get best values for day over all listings
    df = df.dropna(axis=0, how='all')
    # df = df.dropna(axis=1, how='all')
    df['best'] = df.min(axis=1)
    df['mean'] = df['best'].rolling(window=c.ROLLING_AVERAGE, min_periods=1).mean()
    df['saving'] = df['mean'] - df['best']

    # finally update game
    best_listing = best_listing_by_game(game)
    if best_listing and len(df):
        game.shop_best = best_listing.shop
        game.shop_in_stock = True
        game.shop_price = best_listing.price
        last_row = df.iloc[-1]
        game.shop_mean = last_row['mean']
        game.shop_saving = last_row['saving']
        logger.info(
            f'Updated {game} with {game.shop_best.name}: ins={game.shop_in_stock} '
            f'best={game.shop_price} mean={game.shop_mean} saving={game.shop_saving}'
        )
    else:
        # do not delete, it is just out of stock (has been in shop, so good to keep)
        game.shop_best = None
        game.shop_in_stock = False
        game.shop_price = None
        game.shop_mean = None
        game.shop_saving = None
        logger.info(f'Updated {game} but no shop with stock.')
    game.shop_outdated = False
    game.shop_updated_at = timezone.now()
    game.save()


def auto_assign_games():
    """Auto assign games from search."""
    logger.info('Auto assign games from search...')

    listings = list(Listing.objects.filter(bgg_id__isnull=True, bgg_missing=False))

    total = len(listings)
    logger.info(f'Found {total} listings to assign.')

    if total == 0:
        logger.info('No new games to assign.')
        return

    random.shuffle(listings)
    for ix, listing in enumerate(listings):
        name = listing.name
        name = name.replace('(Pre-loved)', '')
        name = name.replace('(Pre-Loved)', '')
        name = name.replace('Bundle', '')
        bgg = search_bgg(name.strip())
        if not bgg['bgg_id']:
            logger.warning(f'{ix}/{total} No bgg game found for {listing}')
            listing.bgg_missing = True
            listing.save()
            continue

        listing.bgg_id = bgg['bgg_id']
        listing.bgg_missing = False
        listing.save()
        logger.info(f'{ix}/{total} Successfully assigned {bgg["name"]} to {listing}')


def clean_games():
    """Clean games with no listings."""
    logger.info('Cleaning games with no listings...')

    games = list(Game.objects.filter(listings__isnull=True))

    total = len(games)
    logger.info(f'Found {total} games to clear.')

    for ix, game in enumerate(games):
        game.delete()
        logger.info(f'{ix}/{total} cleared {game}')
