import json
import logging
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

from main.constants import LABEL_CATEGORY, LABEL_FAMILY, LABEL_MECHANIC, LABEL_SUBDOMAIN
from main.errors import (
    BggGameNotFoundError,
    RedirectError,
    RequestsError,
    ScrapeError,
    TooManyRequestsError,
)
from main.models import Game, Label
from main.selectors import best_listing_by_game, get_best_savings_games, get_today

logger = logging.getLogger(__name__)

# URL_LOGIN = 'https://boardgamegeek.com/login/api/v1'
# URL_CURRENT = 'https://boardgamegeek.com/api/accounts/current'
# URL_RANKINGS = r'https://www.boardgamegeek.com/browse/boardgame/page/'
# URL_HOTNESS = r'https://boardgamegeek.com/xmlapi2/hot?boardgame'
# URL_THING = r'https://boardgamegeek.com/xmlapi2/thing?id={bgg_id}'
URL_GAME = r'https://www.boardgamegeek.com/boardgame/{bgg_id}'
# URL_GAME_DETAILS = r'https://api.geekdo.com/api/geekitems?nosession=1&objectid={bgg_id}&objecttype=thing&subtype=boardgame'  # noqa: E501
# URL_GAME_RATINGS = r'https://api.geekdo.com/api/collections?ajax=1&objectid={bgg_id}&objecttype=thing&oneperuser=1&rated=1&require_review=true&sort=review_tstamp&showcount=50&pageid={p}'  # noqa: E501
# URL_GAME_NUMPLAYERS = r'https://www.boardgamegeek.com/geekitempoll.php?action=view&itempolltype=numplayers&objectid={bgg_id}&objecttype=thing'  # noqa: E501
# URL_GAME_NUMPLAYERS_RESULTS = (
#     r'https://www.boardgamegeek.com/geekpoll.php?action=results&pollid={poll_id}'
# )
# URL_PLAYER_RATINGS = r'https://www.boardgamegeek.com/geekcollection.php?ajax=1&action=collectionpage&username={nick}&gallery=&sort=rating&sortdir=desc&page=&pageID={page}&ff=1&hiddencolumns=&publisherid=&searchstr=&rankobjecttype=subtype&rankobjectid=1&columns[]=title&columns[]=rating&columns[]=bggrating&columns[]=comment&minrating=&rating=&minbggrating=&bggrating=&minplays=&maxplays=&searchfield=title&geekranks=Board%20Game%20Rank&subtype=boardgame&excludesubtype=boardgameexpansion&own=both&trade=both&want=both&wanttobuy=both&prevowned=both&comment=both&wishlist=both&rated=both&played=both&wanttoplay=both&preordered=both&hasparts=both&wantparts=both&wishlistpriority='  # noqa: E501


sleep_time = 0
last_url = ''
last_params = dict()


@retry((TooManyRequestsError, RequestsError), delay=5, jitter=1, max_delay=60, tries=2)
def get(
    url: str, params: dict = None, headers: dict = None, redirect: bool = False
) -> requests.Response:
    """Helper function to do back off fetches with requests."""
    global sleep_time  # noqa PLW0603
    global last_url  # noqa PLW0603
    global last_params  # noqa PLW0603

    if url == last_url and params == last_params:
        sleep_time = round(sleep_time + 0.5, 3)
        logger.info(f'Same url: increased sleep time to {sleep_time} for {url} with {params}')
    elif sleep_time:
        sleep_time = round(sleep_time - 0.005, 3)
    last_url = url
    last_params = params
    sleep(sleep_time)

    headers_default = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0',  # noqa E501
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
        logger.error(f'Too many requests: {res.content} for {url}')
        raise TooManyRequestsError()
    elif res.status_code >= requests.codes.server_error:
        logger.error(f'Server error! {url}')
        raise TooManyRequestsError()
    elif requests.codes.moved <= res.status_code < requests.codes.bad_request:
        logger.error(f'Redirect required: {url}')
        raise RedirectError()

    try:
        res.raise_for_status()
    except requests.RequestException as exc:
        logger.error(f'request bad status: {exc}')

    return res


# def scrape_rankings() -> list[Game]:
#     """Scrape the ranking from boardgamegeek."""
#     logger.info('Scraping rankings...')
#     games = []
#     name_pattern = re.compile(r'(.*)\s\((-?\d+)\)')
#     id_pattern = re.compile(r'/(?:boardgame|boardgameexpansion)/(\d+)/')
#     for page in range(1, 11):
#         rankings_url = f'{URL_RANKINGS}{page}'
#         res = get(rankings_url)
#         html = BeautifulSoup(res.text, 'html.parser')
#         rows = html.find_all('tr', id='row_')
#         logger.info(f'Found {len(rows)} rows for page {page}...')
#         if not rows:
#             return
#
#         for row in rows:
#             tds = row.find_all('td')
#             rank = tds[0].text.strip()
#             url = tds[1].find('a')['href']
#             id_matches = id_pattern.search(url)
#             try:
#                 bgg_id = id_matches.group(1)
#             except AttributeError:
#                 logger.error(f'Could not scrape: no id from {url}')
#                 raise
#             name_year = tds[2].find_all('div')[1].text.strip()
#             name_matches = name_pattern.search(name_year)
#             try:
#                 name = name_matches.group(1)
#                 year = int(name_matches.group(2))
#             except AttributeError:
#                 logger.error(f'Could not scrape: no name/year from {name_year}')
#                 continue
#             game, created = Game.objects.update_or_create(
#                 bgg_id=bgg_id,
#                 defaults={
#                     'rank': int(rank),
#                     'url': url,
#                     'name': name,
#                     'year': year,
#                 },
#             )
#             logger.info(f'{created and "Created" or "Updated"} {game}')
#             games.append(game)
#             if created:
#                 logger.info(f'New game! Stopping with {game}')
#                 break
#     logger.info('Finished scraping rankings')
#     return games
#
#
# def scrape_hotness() -> list[Game]:
#     """Scrape boardgamegeek api hotness."""
#     return
#     logger.info('Scraping hotness...')
#     games = []
#     res = get(URL_HOTNESS)
#     soup = BeautifulSoup(res.content, 'xml')
#     items = soup.find_all('item')
#     for item in items[:10]:
#         bgg_id = item['id']
#         rank = 10_000 + int(item['rank'])
#         name = item.find('name')['value']
#         year = item.find('yearpublished')['value']
#         try:
#             scrape_thing(bgg_id)
#         except NotBoardGameTypeError:
#             logger.info(f'#{rank} {name} [{year}] is not a boardgame')
#             continue
#         game, created = Game.objects.get_or_create(
#             bgg_id=bgg_id,
#             defaults={
#                 'rank': int(rank),
#                 'url': f'/boardgame/{bgg_id}',
#                 'name': name,
#                 'year': year,
#             },
#         )
#         logger.info(f'{created and "Created" or "Existing"} {game}')
#         games.append(game)
#         if created:
#             logger.info(f'New game! Stopping with {game}')
#             break
#     logger.info('Finished scraping hotness!')
#     return games
#
#
# def delete_most_insignificant_games():
#     """Delete games to reduce reviews count."""
#     logger.info('Deleting oldest games...')
#     total_reviews_cnt = Review.objects.count()
#     if total_reviews_cnt < REVIEW_COUNT_LIMIT:
#         logger.info(f'Not enough reviews to delete games: {total_reviews_cnt}')
#         return
#
#     # Calculate the date one year ago from today
#     one_year_ago = now() - timedelta(days=365)
#     # two_year_ago = now() - timedelta(days=365 * 2)
#
#     # Query to find the game with the fewest reviews in the past year
#     games_with_fewest_reviews = Game.objects.filter(
#         created_at__lt=one_year_ago, reviews_cnt__isnull=False, shop_in_stock=False
#     ).order_by('reviews_cnt')
#     for ix, game in enumerate(games_with_fewest_reviews):
#         game.delete()
#         total_reviews_cnt_after = Review.objects.count()
#         logger.info(
#             f'Deleting {game}: cleared {total_reviews_cnt - total_reviews_cnt_after} reviews'
#         )
#         total_reviews_cnt = total_reviews_cnt_after
#         if ix >= DAILY_DELETE_LIMIT:
#             break
#
#
# def update_game_details_and_reviews():
#     """Updating games."""
#     logger.info('Updating already scraped games...')
#     days_ago = 5
#     total_game_cnt = Game.objects.count()
#     daily_cut = total_game_cnt // days_ago
#     time_ago = now() - timedelta(days=days_ago)
#     games = Game.objects.filter(scraped_at__lt=time_ago).all()[:daily_cut]
#     for ix, game in enumerate(games):
#         logger.info(f'Progress {ix}/{len(games)}')
#         scrape_game(game)


@retry((OperationalError, ScrapeError), delay=3, jitter=3, max_delay=30)
def scrape_game(bgg_id: int) -> Game:
    """Scrape the game from boardgamegeek."""
    logger.info(f'Scraping {bgg_id}...')
    url = URL_GAME.format(bgg_id=bgg_id)
    res = get(url, redirect=True)

    if 'Item not found' in res.text:
        raise BggGameNotFoundError()

    matches = re.search(r'GEEK\.geekitemPreload\s=\s(.*)GEEK\.geekitemSettings', res.text, re.S)
    json_match = matches.groups()[0]
    preload = json.loads(json_match.strip().rstrip(';'))
    if 'item' not in preload:
        raise ScrapeError('no preload script found')

    # get instance
    try:
        game = Game.objects.get(id=bgg_id)
    except Game.DoesNotExist:
        game = Game()

    # info
    game.name = preload['item']['name']
    game.slug = slugify(unidecode(game.name))
    game.label = preload['item']['label']
    game.year = int(preload['item']['yearpublished'])
    game.url = res.request.url
    game.rank = int(preload['item']['rankinfo'][0]['rank']) or None
    game.img = preload['item']['imageurl'].replace('\\', '')
    description_html = preload['item']['description'].replace('\\', '').replace('\n', ' ')
    description = BeautifulSoup(description_html, 'html.parser').text
    game.description = description.replace('  ', ' ').strip()

    if game.label == 'Board Game':
        game = scrape_boardgame_details(bgg_id, game, preload)
    elif game.label in ['RPG Item']:
        pass
    else:
        raise NotImplementedError(f'Unknown label: {game.label}')

    game.scraped_at = timezone.now()
    game.save()

    logger.info(f'Saved game {game}')
    return game


def scrape_boardgame_details(bgg_id, game, preload):
    """Get specific boardgame details."""
    # basic details
    game.rating = float(preload['item']['stats']['average'])
    game.min_players = preload['item']['minplayers']
    game.max_players = preload['item']['maxplayers']
    game.min_play_time = preload['item']['minplaytime']
    game.max_play_time = preload['item']['maxplaytime']
    game.min_age = preload['item']['minage']
    game.pitch = preload['item']['short_description']

    # polls
    polls = preload['item']['polls']
    game.weight_avg = float(polls['boardgameweight']['averageweight'])
    if polls['userplayers']['recommended']:
        game.rec_min_players = polls['userplayers']['recommended'][0]['min']
        game.rec_max_players = polls['userplayers']['recommended'][0]['max'] or 8
    if polls['userplayers']['best']:
        game.best_min_players = polls['userplayers']['best'][0]['min']
        game.best_max_players = polls['userplayers']['best'][0]['max'] or 8
    with suppress(ValueError):
        game.rec_min_age = int(polls['playerage'].rstrip('+').partition('–')[0])

    # labels (require game to be saved)
    if not game.pk:
        game.id = bgg_id
        game.save()
    game_links_labels = {
        'boardgamecategory': ('categories', LABEL_CATEGORY),
        'boardgamemechanic': ('mechanics', LABEL_MECHANIC),
        'boardgamefamily': ('families', LABEL_FAMILY),
        'boardgamesubdomain': ('subdomains', LABEL_SUBDOMAIN),
    }
    for key, val in game_links_labels.items():
        data = []
        for link_item in preload['item']['links'][key]:
            label, _ = Label.objects.get_or_create(
                id=link_item['objectid'], defaults={'type': val[1], 'name': link_item['name']}
            )
            data.append(label)
        getattr(game, val[0]).set(data)

    return game


def search_bgg(name: str) -> dict | None:
    """Search BGG for game by name."""
    host = 'https://boardgamegeek.com/geeksearch.php'
    params = {
        'objecttype': 'boardgame',
        'action': 'search',
        'q': name,
    }
    res = get(host, params)

    soup = BeautifulSoup(res.content, 'html.parser')
    if 'No Items Found' in soup.text:
        name_cut = ' '.join(name.split()[1:-1]).strip()
        if name_cut:
            return search_bgg(name_cut)
        return {
            'name': 'not_found',
            'bgg_id': None,
            'missing': True,
            'image': None,
            'search': res.request.url,
        }

    table = soup.find('table', id='collectionitems')
    first_row = table.find_all('tr')[1]
    tds = first_row.find_all('td')
    second_cell = tds[1]
    try:
        image_url = second_cell.find('img')['src']
    except TypeError:
        return {
            'name': 'not_found',
            'bgg_id': None,
            'missing': True,
            'image': None,
            'search': res.request.url,
        }
    third_cell = tds[2]
    anchor = third_cell.find('a')
    game_name = anchor.text.strip()
    href = anchor['href']
    bgg_id = href.split('/')[2]
    return {
        'name': game_name,
        'bgg_id': bgg_id,
        'missing': False,
        'image': image_url,
        'search': res.request.url,
    }


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


def update_outdated_game_shop_prices():
    """Update outdated shop prices on games."""
    games = list({*Game.objects.filter(shop_outdated=True).all(), *get_best_savings_games()})
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
    df['mean'] = df['best'].rolling(window=365, min_periods=1).mean()
    df['saving'] = df['mean'] - df['best']

    # finally update game
    best_listing = best_listing_by_game(game)
    if best_listing:
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
