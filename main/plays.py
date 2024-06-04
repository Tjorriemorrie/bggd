import logging
import xml.etree.ElementTree as Et
from datetime import datetime

import pytz
from django.db.models import Max
from django.utils.timezone import now

from main.models import Day, Game, Play, Player
from main.scraper import get

logger = logging.getLogger(__name__)


def scrape_plays(player: Player):
    """Scrape plays for player."""
    url = 'https://www.boardgamegeek.com/xmlapi2/plays'
    params = {
        'username': player.nick,
        'type': 'thing',
        'subtype': 'boardgame',
        'page': 0,
    }
    while True:
        params['page'] += 1
        logger.info(f'Scraping plays for {params}')
        res = get(url, params=params)
        root = Et.fromstring(res.content)  # noqa S314
        plays = root.findall('play')
        if not plays:
            logger.info('No more plays')
            break
        for play_elem in plays:
            bgg_id = int(play_elem.attrib['id'])
            game_id = int(play_elem.find('item').attrib['objectid'])
            try:
                game = Game.objects.get(bgg_id=game_id)
            except Game.DoesNotExist:
                logger.info(f'Game {game_id} not scraped yet: {play_elem.find("item")}')
                continue
            duration = int(play_elem.attrib['length']) or None
            num_players = (
                len(players_elem.findall('player'))
                if (players_elem := play_elem.find('players')) is not None
                else None
            )
            day = Day.get_day_at(play_elem.attrib['date'])
            if day > now():
                day = now()
            play, created = Play.objects.update_or_create(
                bgg_id=bgg_id,
                defaults={
                    'game': game,
                    'player': player,
                    'day': day,
                    'duration': duration,
                    'num_players': num_players,
                },
            )
            if created:
                logger.info(f'{"Created" if created else "Updated"} {play}')

        update_stats_for_plays(player)


def update_stats_for_plays(player):
    """Updates the review with play count and last date."""
    for review in player.reviews.all():
        num_plays = Play.objects.filter(player=player, game=review.game).count()
        review.num_plays = num_plays

        # Get the last datetime of plays for the player and game
        last_played_at = Day.objects.filter(
            plays__player=player, plays__game=review.game
        ).aggregate(last_played_at=Max('day'))
        # Check if last_played_at is not None before assigning
        if last_played_at['last_played_at'] is not None:
            dt = last_played_at['last_played_at']
            review.last_played_at = datetime(dt.year, dt.month, dt.day, tzinfo=pytz.UTC)
        else:
            review.last_played_at = None
        review.save()
