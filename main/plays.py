"""Read a player's BGG plays and turn them into what to play next.

Plays are replayed oldest first. On each play day the top `TOP_K` by score is
drawn from the games already played before that day. Every play counts for the
game played, and every top-k game that was not played is skipped once for each
play that day. A game on its first play day is played because it is new, not
chosen over the suggestions, so it counts as one play and skips none. A game's
score is its play rate, plays against skips, raised by up to double for the days
since it was last played and since it was last skipped: liked games lead, a game
left on the shelf comes round again, one just passed over steps aside, and one
always skipped fades however long it waits.
"""

import logging
import math
from bisect import bisect_left
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import caches
from django.utils import timezone

from main.models import OwnedGame, Play, Player

logger = logging.getLogger(__name__)

URL_USER = 'https://boardgamegeek.com/xmlapi2/user'
URL_COLLECTION = 'https://boardgamegeek.com/xmlapi2/collection'
URL_PLAYS = 'https://boardgamegeek.com/xmlapi2/plays'

# One sync reads at most this many pages of 100 plays, newest first.
PLAYS_MAX_PAGES = 10
PLAYS_PER_PAGE = 100
# The browser saves a fetched page this many plays per request.
PLAYS_CHUNK = 20

# Both the suggestions shown and the games each play day is scored against.
TOP_K = 3
# The share of a game's play rate it scores however recently it was played or
# skipped; the rest it earns back by waiting, in full for the longest wait.
RATE_WEIGHT = 1 / 2
# A game not played in this many years, and skipped since, is marked to sell.
SELL_IDLE_YEARS = 2

# One request per call: the caller is a web request inside gunicorn's timeout,
# so there is no retry loop here.
BGG_TIMEOUT = 20


class BggPlaysError(Exception):
    """BGG answered a plays sync request with an error."""


def _bgg_get(url: str, params: dict) -> requests.Response:
    """Make one authorised BGG XML API2 request."""
    headers = {'Authorization': f'Bearer {settings.BGG_AUTH}'}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=BGG_TIMEOUT)
    except requests.RequestException as exc:
        logger.error(f'❌ BGG request failed: url={url}, params={params}, error={exc}')
        raise BggPlaysError(f'Could not reach BGG: {exc}') from exc
    if res.status_code >= requests.codes.bad_request:
        logger.error(
            f'❌ BGG refused request: url={url}, params={params}, status={res.status_code}'
        )
        raise BggPlaysError(f'BGG answered {res.status_code}')
    logger.info(f'🎲 BGG answered: url={url}, params={params}, status={res.status_code}')
    return res


def fetch_bgg_user(username: str) -> dict | None:
    """Fetch a BGG user's public profile, or None when the name is unknown."""
    res = _bgg_get(URL_USER, {'name': username})
    user = BeautifulSoup(res.content, 'xml').find('user')
    # BGG answers an unknown name with an empty id rather than an error.
    if not user or not user.get('id'):
        logger.warning(f'⚠️ BGG user not found: username={username}')
        return None

    def value(tag: str) -> str:
        elem = user.find(tag)
        return (elem.get('value') or '').strip() if elem else ''

    full_name = f'{value("firstname")} {value("lastname")}'.strip()
    avatar = value('avatarlink')
    profile = {
        'username': user.get('name') or username,
        'display_name': full_name or user.get('name') or username,
        'avatar': avatar if avatar and avatar != 'N/A' else None,
        'year_registered': value('yearregistered') or None,
    }
    logger.info(f'🎲 Fetched BGG user: username={profile["username"]}')
    return profile


def get_or_create_player(username: str, display_name: str = '') -> Player:
    """Get the stored player for a BGG username, creating it on first sight."""
    player, created = Player.objects.get_or_create(
        username=username.strip().lower(), defaults={'display_name': display_name}
    )
    if display_name and player.display_name != display_name:
        player.display_name = display_name
        player.save(update_fields=['display_name', 'updated_at'])
    logger.info(f'🎲 Player ready: username={player.username}, created={created}')
    return player


def sync_owned(player: Player) -> int | None:
    """Replace the player's owned base games with BGG's, or None while BGG queues it."""
    params = {'username': player.username, 'own': 1, 'excludesubtype': 'boardgameexpansion'}
    res = _bgg_get(URL_COLLECTION, params)
    # BGG builds a collection in the background and answers 202 until it is ready.
    if res.status_code == requests.codes.accepted:
        logger.info(f'🎲 Collection queued by BGG: username={player.username}')
        return None

    soup = BeautifulSoup(res.content, 'xml')
    error = soup.find('error')
    if error:
        message = error.get_text(strip=True)
        logger.error(f'❌ BGG collection error: username={player.username}, error={message}')
        raise BggPlaysError(message)

    owned = {}
    for item in soup.find_all('item'):
        bgg_id = int(item['objectid'])
        name = item.find('name')
        thumbnail = item.find('thumbnail')
        owned[bgg_id] = OwnedGame(
            player=player,
            bgg_id=bgg_id,
            name=name.get_text(strip=True) if name else str(bgg_id),
            thumbnail=thumbnail.get_text(strip=True) if thumbnail else None,
        )
    OwnedGame.objects.filter(player=player).delete()
    OwnedGame.objects.bulk_create(owned.values())
    logger.info(f'🎲 Synced owned games: username={player.username}, owned={len(owned)}')
    return len(owned)


def fetch_plays_page(username: str, page: int) -> tuple[int, list[dict]]:
    """Fetch one page of a user's plays, newest first, with the user's total play count."""
    res = _bgg_get(URL_PLAYS, {'username': username, 'page': page})
    soup = BeautifulSoup(res.content, 'xml')
    root = soup.find('plays')
    if not root:
        error = soup.find('error') or soup.find('message')
        message = error.get_text(strip=True) if error else 'no plays in answer'
        logger.error(f'❌ BGG plays error: username={username}, page={page}, error={message}')
        raise BggPlaysError(message)

    plays = []
    skipped = 0
    for elem in root.find_all('play'):
        item = elem.find('item')
        try:
            played_on = datetime.strptime(elem.get('date', ''), '%Y-%m-%d').date()
        except ValueError:
            # Plays logged without a date ("0000-00-00") cannot be placed in time.
            skipped += 1
            continue
        if not item:
            skipped += 1
            continue
        plays.append(
            {
                'id': int(elem['id']),
                'bgg_id': int(item['objectid']),
                'name': item.get('name', ''),
                'played_on': played_on,
                'quantity': int(elem.get('quantity') or 1),
                'incomplete': elem.get('incomplete') == '1',
            }
        )
    total = int(root.get('total') or 0)
    logger.info(
        f'🎲 Fetched plays page: username={username}, page={page}, '
        f'plays={len(plays)}, skipped={skipped}, total={total}'
    )
    return total, plays


def upsert_plays(player: Player, plays: list[dict]) -> dict:
    """Upsert a batch of plays, counting how many were created and updated."""
    stored = Play.objects.in_bulk([play['id'] for play in plays])
    created = updated = 0
    for play in plays:
        existing = stored.get(play['id'])
        if existing is None:
            Play.objects.create(player=player, **play)
            created += 1
        elif existing.player_id != player.id or any(
            getattr(existing, field) != value for field, value in play.items()
        ):
            existing.player = player
            for field, value in play.items():
                setattr(existing, field, value)
            existing.save()
            updated += 1
    logger.info(
        f'🎲 Upserted plays: username={player.username}, plays={len(plays)}, '
        f'created={created}, updated={updated}'
    )
    return {'created': created, 'updated': updated}


def _staged_key(username: str, page: int) -> str:
    """Cache key of a fetched page waiting to be saved."""
    return f'plays-page:{username}:{page}'


def stage_plays_page(player: Player, page: int) -> dict:
    """Fetch one page of plays from BGG and hold it in the plays cache until it is saved."""
    total, plays = fetch_plays_page(player.username, page)
    staged = {'plays': plays, 'done': 0, 'created': 0, 'updated': 0}
    caches['plays'].set(_staged_key(player.username, page), staged)
    result = {
        'page': page,
        'total': total,
        'total_pages': math.ceil(total / PLAYS_PER_PAGE),
        'size': len(plays),
    }
    logger.info(
        f'🎲 Staged plays page: username={player.username}, page={page}, '
        f'plays={len(plays)}, total={total}'
    )
    return result


def save_staged_chunk(player: Player, page: int) -> dict | None:
    """Save the next chunk of a staged page; None once the page is no longer staged.

    The page is caught up when it is finished and none of its plays were new or
    changed, which means everything older is stored as well.
    """
    cache = caches['plays']
    key = _staged_key(player.username, page)
    staged = cache.get(key)
    if staged is None:
        logger.warning(f'⚠️ No staged plays page: username={player.username}, page={page}')
        return None

    start = staged['done']
    chunk = staged['plays'][start : start + PLAYS_CHUNK]
    counts = upsert_plays(player, chunk)
    staged['done'] += len(chunk)
    staged['created'] += counts['created']
    staged['updated'] += counts['updated']
    finished = staged['done'] >= len(staged['plays'])
    caught_up = False
    if finished:
        cache.delete(key)
        caught_up = bool(staged['plays']) and not staged['created'] and not staged['updated']
        player.synced_at = timezone.now()
        player.save(update_fields=['synced_at', 'updated_at'])
    else:
        # Setting it again restarts the timeout, so only an abandoned page expires.
        cache.set(key, staged)
    result = {
        'done': staged['done'],
        'size': len(staged['plays']),
        'created': staged['created'],
        'updated': staged['updated'],
        'finished': finished,
        'caught_up': caught_up,
    }
    logger.info(
        f'🎲 Saved plays chunk: username={player.username}, page={page}, '
        f'done={staged["done"]}/{len(staged["plays"])}, created={staged["created"]}, '
        f'updated={staged["updated"]}, caught_up={caught_up}'
    )
    return result


@dataclass
class GameScore:
    bgg_id: int
    name: str
    losses: int = 0
    plays: int = 0
    first_played: date | None = None
    last_played: date | None = None
    last_skipped: date | None = None
    score: float = math.inf
    rank: int | None = None
    thumbnail: str | None = None
    stars: int | None = None
    heat: int | None = None
    sell: bool = False

    @property
    def n(self) -> int:
        """Number of times the game was played or skipped."""
        return self.plays + self.losses

    @property
    def mu(self) -> float | None:
        """Share of plays among the times it was played or skipped, or None before either."""
        return self.plays / self.n if self.n else None


@dataclass
class Scoreboard:
    games: dict[int, GameScore]
    rounds: int

    def ranked(self) -> list[GameScore]:
        """Games in the pool, best score first."""
        return sorted(self.games.values(), key=lambda g: (-g.score, g.bgg_id))


def score(game: GameScore, played_share: float, seen_share: float) -> float:
    """Play rate, half of it outright and half earned back by waiting.

    A quarter is earned by the wait since last played and a quarter by the wait
    since last played or skipped, so a skip since the last play counts against
    the game. Each wait is given as its share of the pool's waits, 0 for the
    shortest and 1 for the longest. The rate multiplies the waiting rather than
    adding to it, so a game that is always skipped fades however long it waits,
    and a game always played is never below half its rate.
    """
    waited = (played_share + seen_share) / 2
    return game.mu * (RATE_WEIGHT + (1 - RATE_WEIGHT) * waited)


def _scores(pool: dict[int, GameScore], day: date) -> dict[int, float]:
    """Every pool game's score on `day`, its waits ranked against the others'.

    A wait's share is how many games have waited less, out of the rest: ranking
    rather than dividing by the longest wait keeps one game unplayed for years
    from shrinking every other game's wait to nothing.
    """
    played = {g.bgg_id: (day - g.last_played).days for g in pool.values()}
    seen = {
        g.bgg_id: (day - max(g.last_played, g.last_skipped or g.last_played)).days
        for g in pool.values()
    }
    others = max(len(pool) - 1, 1)
    played_sorted, seen_sorted = sorted(played.values()), sorted(seen.values())
    return {
        bgg_id: score(
            game,
            bisect_left(played_sorted, played[bgg_id]) / others,
            bisect_left(seen_sorted, seen[bgg_id]) / others,
        )
        for bgg_id, game in pool.items()
    }


def _top(pool: dict[int, GameScore], day: date, k: int) -> list[GameScore]:
    """The k pool games with the best score on `day`, ties broken by bgg_id."""
    scores = _scores(pool, day)
    return sorted(pool.values(), key=lambda g: (-scores[g.bgg_id], g.bgg_id))[:k]


def score_games(
    plays: Iterable,
    owned: dict[int, str],
    k: int = TOP_K,
    today: date | None = None,
) -> Scoreboard:
    """Replay plays of owned games oldest first, then score each game as of `today`.

    `today` defaults to the last play day.
    """
    # Plays per game per day; a game played twice that day is rated twice.
    days: dict[date, dict[int, int]] = {}
    kept = 0
    for play in plays:
        if play.incomplete or play.bgg_id not in owned:
            continue
        played = days.setdefault(play.played_on, {})
        played[play.bgg_id] = played.get(play.bgg_id, 0) + play.quantity
        kept += play.quantity
    logger.info(f'🎲 Scoring plays: kept={kept}, play_days={len(days)}, owned={len(owned)}')

    pool: dict[int, GameScore] = {}
    rounds = new_plays = 0
    for day in sorted(days):
        played = days[day]
        # A game on its first play day was played because it is new, not chosen
        # over the suggestions: it counts as one play and skips none of them.
        new = {bgg_id for bgg_id in played if bgg_id not in pool}
        rated = sum(count for bgg_id, count in played.items() if bgg_id not in new)
        losers = [g for g in _top(pool, day, k) if g.bgg_id not in played] if rated else []
        for bgg_id in sorted(played):
            game = pool.get(bgg_id) or GameScore(bgg_id, owned[bgg_id], first_played=day)
            game.plays += 1 if bgg_id in new else played[bgg_id]
            game.last_played = day
            pool[bgg_id] = game
        for loser in losers:
            loser.losses += rated
            loser.last_skipped = day
        rounds += rated + len(new)
        new_plays += sum(played[bgg_id] for bgg_id in new)

    today = today or max(days, default=None)
    scores = _scores(pool, today)
    for rank, game in enumerate(_top(pool, today, len(pool)), start=1):
        game.score = scores[game.bgg_id]
        game.rank = rank
    logger.info(
        f'🎲 Scored games: pool={len(pool)}, rounds={rounds}, '
        f'new_game_plays={new_plays}, today={today}'
    )
    return Scoreboard(games=pool, rounds=rounds)


def priority_stars(games: list[GameScore], most: int = 5) -> list[int]:
    """Min-max scale the games' scores onto 1..most stars; a game never compared gets most."""
    settled = [game.score for game in games if math.isfinite(game.score)]
    low, high = (min(settled), max(settled)) if settled else (0.0, 0.0)
    stars = []
    for game in games:
        if not math.isfinite(game.score) or high == low:
            stars.append(most)
        else:
            stars.append(1 + round((most - 1) * (game.score - low) / (high - low)))
    logger.info(f'🎲 Rated suggestions: games={len(games)}, stars={stars}')
    return stars


def is_sell(game: GameScore, today: date) -> bool:
    """Whether a game went unplayed for `SELL_IDLE_YEARS` and was skipped since.

    The skip since its last play means play days went on without it, so a player
    who simply stopped logging plays has nothing marked to sell.
    """
    idle = today - game.last_played
    skipped_since = game.last_skipped is not None and game.last_skipped > game.last_played
    return skipped_since and idle.days >= 365 * SELL_IDLE_YEARS


def player_report(player: Player) -> dict:
    """Score a stored player's plays into suggestions and the full table."""
    owned = dict(player.owned_games.values_list('bgg_id', 'name'))
    thumbs = dict(player.owned_games.values_list('bgg_id', 'thumbnail'))
    today = timezone.localdate()
    board = score_games(player.plays.all().order_by('played_on'), owned, today=today)
    ranked = board.ranked()
    for game in ranked:
        game.thumbnail = thumbs.get(game.bgg_id)
        game.sell = is_sell(game, today)
    # Rows are inked by play rate, green for the highest to red for the lowest,
    # by its place among the rates: by value, one game at 100% left the rest red.
    rates = sorted(game.mu for game in ranked)
    for game in ranked:
        game.heat = 100 - round(100 * bisect_left(rates, game.mu) / max(len(rates) - 1, 1))
    never = [
        {'bgg_id': bgg_id, 'name': name, 'thumbnail': thumbs.get(bgg_id)}
        for bgg_id, name in sorted(owned.items(), key=lambda kv: kv[1].lower())
        if bgg_id not in board.games
    ]
    suggestions = ranked[:TOP_K]
    for game, stars in zip(suggestions, priority_stars(suggestions), strict=True):
        game.stars = stars
    report = {
        'suggestions': suggestions,
        'never': never,
        'ranked': ranked,
        'sell_count': sum(game.sell for game in ranked),
        'sell_years': SELL_IDLE_YEARS,
        'rounds': board.rounds,
        'plays_stored': player.plays.count(),
        'owned_count': len(owned),
    }
    logger.info(
        f'🎲 Built player report: username={player.username}, ranked={len(ranked)}, '
        f'never={len(never)}, sell={report["sell_count"]}'
    )
    return report
