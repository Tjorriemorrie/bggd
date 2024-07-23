import json
import logging
import re
from contextlib import suppress
from datetime import datetime, timedelta
from time import sleep

import requests
from bs4 import BeautifulSoup
from django.db import IntegrityError, OperationalError
from django.db.models import Avg, Count, Q
from django.utils.timezone import make_aware, now
from retry import retry

from main.constants import (
    DAILY_DELETE_LIMIT,
    REVIEW_COUNT_LIMIT,
    REVIEW_STATUS_CHOICES,
    REVIEW_STATUS_NONE,
    ROWS_TABLE_HEADERS,
    SCRAPE_REVIEWS_EXISTING_BUFFER,
)
from main.errors import (
    BadDateError,
    NotBoardGameTypeError,
    PlayerRatingUsernameNotFoundError,
    PlayerScrapeError,
    ScrapeError,
)
from main.models import (
    LABEL_CATEGORY,
    LABEL_FAMILY,
    LABEL_MECHANIC,
    LABEL_SUBDOMAIN,
    Game,
    Label,
    Player,
    Review,
)
from main.stats import outdate_gameday_by_review

logger = logging.getLogger(__name__)

URL_LOGIN = 'https://boardgamegeek.com/login/api/v1'
URL_CURRENT = 'https://boardgamegeek.com/api/accounts/current'
URL_RANKINGS = r'https://www.boardgamegeek.com/browse/boardgame/page/'
URL_HOTNESS = r'https://boardgamegeek.com/xmlapi2/hot?boardgame'
URL_THING = r'https://boardgamegeek.com/xmlapi2/thing?id={bgg_id}'
URL_GAME = r'https://www.boardgamegeek.com/boardgame/{bgg_id}'
URL_GAME_DETAILS = r'https://api.geekdo.com/api/geekitems?nosession=1&objectid={bgg_id}&objecttype=thing&subtype=boardgame'  # noqa: E501
URL_GAME_RATINGS = r'https://api.geekdo.com/api/collections?ajax=1&objectid={bgg_id}&objecttype=thing&oneperuser=1&rated=1&require_review=true&sort=review_tstamp&showcount=50&pageid={p}'  # noqa: E501
URL_GAME_NUMPLAYERS = r'https://www.boardgamegeek.com/geekitempoll.php?action=view&itempolltype=numplayers&objectid={bgg_id}&objecttype=thing'  # noqa: E501
URL_GAME_NUMPLAYERS_RESULTS = (
    r'https://www.boardgamegeek.com/geekpoll.php?action=results&pollid={poll_id}'
)
URL_PLAYER_RATINGS = r'https://www.boardgamegeek.com/geekcollection.php?ajax=1&action=collectionpage&username={nick}&gallery=&sort=rating&sortdir=desc&page=&pageID={page}&ff=1&hiddencolumns=&publisherid=&searchstr=&rankobjecttype=subtype&rankobjectid=1&columns[]=title&columns[]=rating&columns[]=bggrating&columns[]=comment&minrating=&rating=&minbggrating=&bggrating=&minplays=&maxplays=&searchfield=title&geekranks=Board%20Game%20Rank&subtype=boardgame&excludesubtype=boardgameexpansion&own=both&trade=both&want=both&wanttobuy=both&prevowned=both&comment=both&wishlist=both&rated=both&played=both&wanttoplay=both&preordered=both&hasparts=both&wantparts=both&wishlistpriority='  # noqa: E501


class TooManyRequestsError(Exception):
    """Too many http requests."""


class RequestsError(Exception):
    """SSL error from BGG."""


class RedirectError(Exception):
    """Request requires an unexpected redirect."""


sleep_time = 0
last_url = ''


@retry((TooManyRequestsError, RequestsError), delay=5, jitter=1, max_delay=60, tries=2)
def get(
    url: str, params: dict = None, headers: dict = None, redirect: bool = True
) -> requests.Response:
    """Helper function to do back off fetches with requests."""
    global sleep_time  # noqa PLW0603
    global last_url  # noqa PLW0603

    if url == last_url:
        sleep_time = round(sleep_time + 0.5, 3)
        logger.info(f'Increased sleep time to {sleep_time}')
    elif sleep_time:
        sleep_time = round(sleep_time - 0.005, 3)
    last_url = url
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
    except Exception as exc:
        logger.error(f'Connection error! url={url}')
        logger.error(f'Connection error! exc={exc}')
        sleep(5)
        raise RequestsError() from exc

    if res.status_code in [requests.codes.too_many, 430]:
        logger.error(f'Too many requests: {res.content} for {url}')
        raise TooManyRequestsError()
    elif res.status_code >= requests.codes.server_error:
        logger.error(f'Server error! {url}: {res.text}')
        raise TooManyRequestsError()
    elif requests.codes.moved <= res.status_code < requests.codes.bad_request:
        logger.error(f'Redirect required: {url}')
        raise RedirectError()

    res.raise_for_status()
    return res


def scrape_rankings() -> list[Game]:
    """Scrape the ranking from boardgamegeek."""
    logger.info('Scraping rankings...')
    games = []
    name_pattern = re.compile(r'(.*)\s\((-?\d+)\)')
    id_pattern = re.compile(r'/(?:boardgame|boardgameexpansion)/(\d+)/')
    for page in range(1, 11):
        rankings_url = f'{URL_RANKINGS}{page}'
        res = get(rankings_url)
        html = BeautifulSoup(res.text, 'html.parser')
        rows = html.find_all('tr', id='row_')
        logger.info(f'Found {len(rows)} rows for page {page}...')
        if not rows:
            return

        for row in rows:
            tds = row.find_all('td')
            rank = tds[0].text.strip()
            url = tds[1].find('a')['href']
            id_matches = id_pattern.search(url)
            try:
                bgg_id = id_matches.group(1)
            except AttributeError:
                logger.error(f'Could not scrape: no id from {url}')
                raise
            name_year = tds[2].find_all('div')[1].text.strip()
            name_matches = name_pattern.search(name_year)
            try:
                name = name_matches.group(1)
                year = int(name_matches.group(2))
            except AttributeError:
                logger.error(f'Could not scrape: no name/year from {name_year}')
                continue
            game, created = Game.objects.update_or_create(
                bgg_id=bgg_id,
                defaults={
                    'rank': int(rank),
                    'url': url,
                    'name': name,
                    'year': year,
                },
            )
            logger.info(f'{created and "Created" or "Updated"} {game}')
            games.append(game)
            if created:
                logger.info(f'New game! Stopping with {game}')
                break
    logger.info('Finished scraping rankings')
    return games


def scrape_hotness() -> list[Game]:
    """Scrape boardgamegeek api hotness."""
    logger.info('Scraping hotness...')
    games = []
    res = get(URL_HOTNESS)
    soup = BeautifulSoup(res.content, 'xml')
    items = soup.find_all('item')
    for item in items[:10]:
        bgg_id = item['id']
        rank = 10_000 + int(item['rank'])
        name = item.find('name')['value']
        year = item.find('yearpublished')['value']
        try:
            scrape_thing(bgg_id)
        except NotBoardGameTypeError:
            logger.info(f'#{rank} {name} [{year}] is not a boardgame')
            continue
        game, created = Game.objects.get_or_create(
            bgg_id=bgg_id,
            defaults={
                'rank': int(rank),
                'url': f'/boardgame/{bgg_id}',
                'name': name,
                'year': year,
            },
        )
        logger.info(f'{created and "Created" or "Existing"} {game}')
        games.append(game)
        if created:
            logger.info(f'New game! Stopping with {game}')
            break
    logger.info('Finished scraping hotness!')
    return games


def scrape_thing(bgg_id: int):
    """Scrape boardgamegeek thing api endpoint."""
    res = get(URL_THING.format(bgg_id=bgg_id))
    soup = BeautifulSoup(res.content, 'xml')
    item = soup.find('item')
    if item['type'] != 'boardgame':
        raise NotBoardGameTypeError()
    return item


def delete_most_insignificant_games():
    """Delete games to reduce reviews count."""
    total_reviews_cnt = Review.objects.count()
    if total_reviews_cnt < REVIEW_COUNT_LIMIT:
        logger.info(f'Not enough reviews to delete games: {total_reviews_cnt}')
        return

    # Calculate the date one year ago from today
    one_year_ago = now() - timedelta(days=365)
    two_year_ago = now() - timedelta(days=365 * 2)

    # Fetch games that didn't have a review in the past year
    games_without_recent_reviews = Game.objects.filter(created_at__lt=two_year_ago).exclude(
        reviews__reviewed_at__gte=one_year_ago
    )
    logger.info(f'Games without recent reviews: {len(games_without_recent_reviews)}')

    # Query to find the game with the fewest reviews in the past year
    games_with_fewest_reviews = (
        Review.objects.filter(game__created_at__lt=two_year_ago, reviewed_at__gt=one_year_ago)
        .values('game')
        .annotate(review_count=Count('id'))
        .order_by('review_count')
        .all()[:20]
    )
    del_cnt = 0
    for game_info in games_with_fewest_reviews:
        game = Game.objects.get(id=game_info['game'])
        if game.shop_available:
            logger.info(f'{game} is still available.')
            continue
        game.delete()
        total_reviews_cnt_after = Review.objects.count()
        logger.info(
            f'Deleting {game}: cleared {total_reviews_cnt - total_reviews_cnt_after} reviews'
        )
        total_reviews_cnt = total_reviews_cnt_after
        del_cnt += 1
        if del_cnt >= DAILY_DELETE_LIMIT:
            break


def update_game_details_and_reviews():
    """Updating games."""
    logger.info('Updating already scraped games...')
    days_ago = 5
    total_game_cnt = Game.objects.count()
    daily_cut = total_game_cnt // days_ago
    time_ago = now() - timedelta(days=days_ago)
    games = Game.objects.filter(scraped_at__lt=time_ago).all()[:daily_cut]
    for ix, game in enumerate(games):
        logger.info(f'Progress {ix}/{len(games)}')
        scrape_game(game)


def scrape_new_games():
    """Newly added games need to get scraped."""
    logger.info('Scraping new games...')
    games = Game.objects.filter(Q(scraped_at__isnull=True) | Q(weight_avg__isnull=True)).all()
    for ix, game in enumerate(games):
        logger.info(f'Progress {ix}/{len(games)}')
        scrape_game(game)


@retry((OperationalError, ScrapeError), delay=3, jitter=3, max_delay=30)
def scrape_game(game: Game):
    """Scrape the game from boardgamegeek."""
    logger.info(f'Scraping {game}')
    res = get(URL_GAME.format(bgg_id=game.bgg_id))
    matches = re.search(r'GEEK\.geekitemPreload\s=\s(.*)GEEK\.geekitemSettings', res.text, re.S)
    json_match = matches.groups()[0]
    preload = json.loads(json_match.strip().rstrip(';'))

    # basic details
    game.rank = int(preload['item']['rankinfo'][0]['rank']) or 10_000
    game.weight_avg = float(preload['item']['polls']['boardgameweight']['averageweight'])
    game.min_players = preload['item']['minplayers']
    game.max_players = preload['item']['maxplayers']
    game.min_play_time = preload['item']['minplaytime']
    game.max_play_time = preload['item']['maxplaytime']
    game.min_age = preload['item']['minage']
    game.pitch = preload['item']['short_description']
    description_html = preload['item']['description'].replace('\\', '').replace('\n', ' ')
    description = BeautifulSoup(description_html, 'html.parser').text
    game.description = description.replace('  ', ' ').strip()
    game.img = preload['item']['imageurl'].replace('\\', '')

    # polls
    polls = preload['item']['polls']
    if polls['userplayers']['recommended']:
        game.rec_min_players = polls['userplayers']['recommended'][0]['min']
        game.rec_max_players = polls['userplayers']['recommended'][0]['max'] or 8
    if polls['userplayers']['best']:
        game.best_min_players = polls['userplayers']['best'][0]['min']
        game.best_max_players = polls['userplayers']['best'][0]['max'] or 8
    with suppress(ValueError):
        game.rec_min_age = int(polls['playerage'].rstrip('+').partition('–')[0])

    # labels
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
                bgg_id=link_item['objectid'], defaults={'type': val[1], 'name': link_item['name']}
            )
            data.append(label)
        # logger.info(f'Set {len(data)} {val[1]}')
        getattr(game, val[0]).set(data)

    scrape_game_reviews(game)

    game.recs_cnt = game.recs.filter(is_primary=True).count()
    game.scraped_at = now()
    game.save()

    logger.info(f'Saved game {game}')


def scrape_game_reviews(game: Game):
    """Scrape game reviews from boardgamegeek."""
    logger.info(f'Scraping reviews of {game}')
    num_items = 0

    # first run from the front
    p = 0
    existing = 0
    while existing <= SCRAPE_REVIEWS_EXISTING_BUFFER:
        p += 1
        logger.info(f'Scraping page {p}/{num_items // 50 + 1} for reviews...')
        res = get(URL_GAME_RATINGS.format(bgg_id=game.bgg_id, p=p)).json()

        if not res['items']:
            logger.warning(f'No more items found from page {p}!')
            break

        for item in res['items']:
            try:
                review, created = parse_game_review(game, item)
            except BadDateError:
                continue
            existing += not bool(created)
            # logger.info(f'{created and "Created" or "Updated"} {review}')

        if not num_items:
            num_items = res['config']['numitems']

    # then continue at the back
    reviews_cnt = game.reviews.count()
    if reviews_cnt < num_items * 0.999:
        p = reviews_cnt // 50
        while True:
            p += 1
            logger.info(f'Scraping page {p}/{num_items // 50 + 1} for reviews...')
            res = get(URL_GAME_RATINGS.format(bgg_id=game.bgg_id, p=p)).json()

            if not res['items']:
                logger.warning(f'No more items found from page {p}!')
                break

            for item in res['items']:
                try:
                    review, created = parse_game_review(game, item)
                except BadDateError:
                    continue
                reviews_cnt += bool(created)
                # logger.info(f'{created and "Created" or "Updated"} {review}')

    # update rating
    avg_rating = game.reviews.all().aggregate(Avg('rating'))
    game.rating = avg_rating['rating__avg']
    game.reviews_cnt = game.reviews.count()

    logger.info(f'Finished scraping reviews for {game}!')


def parse_game_review(game: Game, item: dict) -> tuple[Review, bool]:  # noqa PLR0912
    """Parse game review from html."""
    item['rating'] = round(float(item['rating']), 1)
    item['rating'] = max([1.0, item['rating']])
    item['rating'] = min([10.0, item['rating']])
    try:
        player, _ = Player.objects.get_or_create(
            nick=item['user']['username'],
            defaults={
                'country': item['user']['country'],
                'avatar': item['user'].get('avatarurl_md'),
            },
        )
    except Player.MultipleObjectsReturned:
        logger.info(f'Found multiple nicks {item["user"]["username"]}')
        raise
    tstamp = item['review_tstamp'] or item['tstamp']
    reviewed_at = make_aware(datetime.strptime(tstamp, '%Y-%m-%d %H:%M:%S'))
    twenty_years_ago = now() - timedelta(weeks=1_040)
    if twenty_years_ago > reviewed_at > now():
        raise BadDateError('reviewed_at')
    try:
        review, created = Review.objects.get_or_create(
            bgg_id=item['collid'],
            defaults={
                'game': game,
                'player': player,
                'rating': item['rating'],
                'reviewed_at': reviewed_at,
            },
        )
    except IntegrityError:
        logger.warning(f'Integrity error on review item {item}!')
        review, created = Review.objects.update_or_create(
            game=game,
            player=player,
            defaults={
                'bgg_id': item['collid'],
                'rating': item['rating'],
                'reviewed_at': reviewed_at,
            },
        )
        logger.warning(f'{created and "Created" or "Updated"} review')
    except Review.MultipleObjectsReturned:
        logger.warning(f'Multiple objects returned for {item}!')
        Review.objects.filter(game=game, player=player).delete()
        return parse_game_review(game, item)

    # mark player as changed only for new reviews, not changes (as below)
    # allows changed players to pick this up
    if created:
        player.last_review_at = now()
        player.is_outdated = True
        player.save()
        # outdate gameday
        outdate_gameday_by_review(review)

    # update existing review if different review tstamp or rating
    if review.reviewed_at != reviewed_at or review.rating != item['rating']:
        logger.info(f'{review} rating changed from {review.rating} to {item["rating"]}')
        review.reviewed_at = reviewed_at
        review.rating = item['rating']
        created = True
        review.save()

    # review status
    for status, _ in REVIEW_STATUS_CHOICES:
        if status not in item['status']:
            continue
        if status == review.status:
            break
        else:
            review.status = status
            review.save()
            break
    else:
        # if item['status'] and settings.DEBUG:
        #     raise Exception(f'unknown statuses: {item["status"]}')
        review.status = REVIEW_STATUS_NONE
        review.save()

    return review, created


@retry(OperationalError, delay=3, jitter=3, max_delay=30)
def scrape_player(player: Player):
    """Scrape the player details."""
    res = get(player.bgg_link)
    html = BeautifulSoup(res.text, 'html.parser')
    avatar_block = html.find('div', class_='avatarblock')
    if not avatar_block:
        raise PlayerScrapeError('user does not exist')
    player.bgg_id = avatar_block['data-userid']
    avatar_divs = avatar_block.find_all('div')
    player.name = avatar_divs[0].text.strip() or None
    with suppress(TypeError):
        player.avatar = avatar_block.find('img', alt='Avatar')['src']
    try:
        country, *areas = avatar_divs[2].stripped_strings
        player.country = country
        player.area = ', '.join(areas)
    except ValueError:
        pass
    player.scraped_at = now()
    player.save()


def scrape_player_ratings(player: Player):  # noqa: PLR0915 PLR0912
    """Scrape the player ratings."""
    orphan_game_ids = list(player.reviews.values_list('game_id', flat=True))
    page = 0
    while True:
        page += 1
        url = URL_PLAYER_RATINGS.format(nick=player.nick, page=page)
        res = get(url)
        html = BeautifulSoup(res.text, 'html.parser')
        table = html.find('table', id='collectionitems')
        try:
            rows = table.find_all('tr')
        except Exception as exc:
            logger.exception(f'No ratings for player URL = {url}')
            raise PlayerRatingUsernameNotFoundError() from exc
        if len(rows) < ROWS_TABLE_HEADERS:
            break
        for row in rows[1:]:
            # bgg id
            bgg_id = int(row['id'].split('_')[-1])
            cells = row.find_all('td')
            # get game
            game_row = cells[0].find('a')['href']
            matches = re.search(r'/boardgame/(\d+)/', game_row)
            game_bgg_id = int(matches.group(1))
            try:
                game = Game.objects.get(bgg_id=game_bgg_id)
            except Game.DoesNotExist:
                unknown_game = cells[0].text.replace('\n', ' ').replace('\r', ' ')
                logger.debug(f'Skipping unknown game {unknown_game}')
                continue
            # get rating
            rating_info = list(cells[1].stripped_strings)
            if rating_info[0] == 'N/A':
                continue
            rating = round(float(rating_info[0]), 1)
            rating = min(10.0, rating)
            rating = max(1.0, rating)
            try:
                rated_on = make_aware(datetime.strptime(rating_info[1].rstrip('*'), '%b %Y'))
            except IndexError:
                # month and year is in next year. just skip.
                continue
            # get comment
            comment_and_date = list(cells[3].stripped_strings)
            comment = comment_and_date[0] if comment_and_date else None

            # update review
            try:
                review = Review.objects.get(game=game, player=player)
                try:  # should always have game id if review exists
                    orphan_game_ids.remove(review.game.id)
                except ValueError:
                    logger.error(
                        f'{review.game.id} not found in remaining game ids {orphan_game_ids}'
                    )
            except Review.DoesNotExist:
                review = Review.objects.create(
                    player=player,
                    game=game,
                    bgg_id=bgg_id,
                    rating=rating,
                    comment=comment,
                    reviewed_at=rated_on,
                )
                logger.info(f'Created missed {review} for existing {game}!')
                continue

            if review.rating != rating or review.comment != comment:
                logger.info(
                    f'Rating for {game} changed from {review.rating} to {rating}: {comment}'
                )
                review.rating = rating
                review.comment = comment
                review.save()

    # remove orphan reviews
    for game_id in orphan_game_ids:
        try:
            review = Review.objects.get(player=player, game_id=game_id)
        except Review.DoesNotExist:
            continue
        logger.info(f'Deleting orphan: {review}')
        review.delete()
