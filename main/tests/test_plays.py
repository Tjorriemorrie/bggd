import math
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from main.models import Play, Player
from main.plays import (
    GameScore,
    _scores,
    _top,
    is_sell,
    priority_stars,
    save_staged_chunk,
    score,
    score_games,
    stage_plays_page,
    upsert_plays,
)

DAY = date(2024, 1, 1)


def play(bgg_id: int, day: int, incomplete: bool = False, quantity: int = 1) -> SimpleNamespace:
    """A stand-in for a stored Play on the given day offset."""
    return SimpleNamespace(
        bgg_id=bgg_id,
        played_on=DAY + timedelta(days=day),
        incomplete=incomplete,
        quantity=quantity,
    )


def owned(*ids: int) -> dict[int, str]:
    """Owned games named after their ids."""
    return {bgg_id: f'Game {bgg_id}' for bgg_id in ids}


class ScoreGamesTest(SimpleTestCase):
    def test_only_the_top_three_are_skipped(self):
        plays = [play(bgg_id, day) for day, bgg_id in enumerate(range(1, 8))]
        plays += [play(7, day) for day in range(7, 13)]
        board = score_games(plays, owned(*range(1, 8)))
        assert (board.games[7].plays, board.games[7].losses) == (7, 0)
        # Each of the six replays of game 7 skips at most the three suggested games.
        assert 0 < sum(g.losses for g in board.games.values()) <= 3 * 6

    def test_games_played_the_same_day_do_not_lose_to_each_other(self):
        plays = [play(1, 0), play(2, 1), play(2, 2), play(1, 3), play(2, 3)]
        board = score_games(plays, owned(1, 2))
        # Day 2: game 1 was suggested and skipped for game 2. Day 3: both played.
        assert (board.games[1].plays, board.games[1].losses) == (2, 1)
        assert (board.games[2].plays, board.games[2].losses) == (3, 0)
        assert board.rounds == 5

    def test_a_new_game_counts_once_and_skips_no_one(self):
        board = score_games([play(1, 0), play(2, 1, quantity=3)], owned(1, 2))
        assert (board.games[2].plays, board.games[2].losses) == (1, 0)
        assert (board.games[1].losses, board.games[1].last_skipped) == (0, None)
        assert board.rounds == 2

    def test_only_plays_of_known_games_skip_the_suggestions(self):
        board = score_games([play(1, 0), play(2, 1), play(2, 2), play(3, 2)], owned(1, 2, 3))
        # Day 2: game 3 is new, so game 1 is skipped once, for the play of game 2.
        assert board.games[1].losses == 1
        assert (board.games[3].plays, board.games[3].losses) == (1, 0)
        assert board.rounds == 4

    def test_a_skip_restarts_the_clock_like_a_play(self):
        board = score_games([play(1, 0), play(2, 1), play(2, 3)], owned(1, 2))
        # Game 1 was suggested and skipped on day 3, so it was last seen then.
        assert board.games[1].last_played == DAY
        assert board.games[1].last_skipped == DAY + timedelta(days=3)
        assert board.games[2].last_skipped is None

    def test_half_the_play_rate_outright_and_a_quarter_for_each_wait(self):
        game = GameScore(1, 'Game', plays=1, losses=1)
        assert score(game, 0, 0) == 0.25
        assert score(game, 1, 0) == 0.375
        assert score(game, 1, 1) == 0.5

    def test_a_long_wait_beats_a_slightly_higher_play_rate(self):
        today = DAY + timedelta(days=2000)
        pool = {
            # Recently played and skipped, a third of the times suggested.
            1: GameScore(
                1,
                'Recent',
                plays=1,
                losses=2,
                last_played=today - timedelta(days=71),
                last_skipped=today - timedelta(days=10),
            ),
            # Long unplayed and unskipped, a quarter of the times suggested.
            2: GameScore(
                2,
                'Waiting',
                plays=1,
                losses=3,
                last_played=today - timedelta(days=657),
                last_skipped=today - timedelta(days=465),
            ),
            # One game unplayed for years must not shrink the others' waits.
            3: GameScore(3, 'Ancient', plays=1, losses=99, last_played=DAY),
        }
        assert [g.bgg_id for g in _top(pool, today, 2)] == [2, 1]

    def test_a_skip_since_the_last_play_counts_against_a_game(self):
        today = DAY + timedelta(days=100)
        pool = {
            1: GameScore(1, 'Unskipped', plays=1, losses=1, last_played=DAY),
            2: GameScore(2, 'Skipped', plays=1, losses=1, last_played=DAY, last_skipped=today),
            3: GameScore(3, 'Fresh', plays=1, losses=1, last_played=today),
        }
        assert [g.bgg_id for g in _top(pool, today, 3)] == [1, 2, 3]
        # A skip before the last play no longer counts.
        pool[2].last_skipped = DAY - timedelta(days=1)
        assert _scores(pool, today)[2] == _scores(pool, today)[1]

    def test_a_game_never_played_when_suggested_fades_however_long_it_waits(self):
        today = DAY + timedelta(days=100)
        pool = {
            1: GameScore(1, 'Shunned', plays=1, losses=999, last_played=DAY),
            2: GameScore(2, 'Liked', plays=1, losses=1, last_played=today - timedelta(days=5)),
        }
        assert [g.bgg_id for g in _top(pool, today, 2)] == [2, 1]

    def test_every_play_in_a_day_is_rated(self):
        board = score_games(
            [play(1, 0), play(2, 1), play(2, 2), play(2, 2), play(2, 2, quantity=2)],
            owned(1, 2),
        )
        assert board.games[2].plays == 5
        assert board.games[1].losses == 4
        assert board.rounds == 6

    def test_unowned_and_incomplete_plays_are_ignored(self):
        plays = [play(1, 0), play(9, 1), play(2, 2, incomplete=True)]
        board = score_games(plays, owned(1, 2))
        assert set(board.games) == {1}
        assert board.rounds == 1


@override_settings(
    CACHES={
        'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
        'plays': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
    }
)
class SyncPlaysPageTest(TestCase):
    def page(self, size: int = 45) -> list[dict]:
        return [
            {
                'id': play_id,
                'bgg_id': 13,
                'name': 'Catan',
                'played_on': DAY + timedelta(days=play_id),
                'quantity': 1,
                'incomplete': False,
            }
            for play_id in range(1, size + 1)
        ]

    def sync(self, player: Player, plays: list[dict]) -> list[dict]:
        """Stage a page of plays and save it chunk by chunk, returning every chunk's answer."""
        with patch('main.plays.fetch_plays_page', return_value=(len(plays), plays)):
            stage_plays_page(player, 1)
        chunks = []
        while not chunks or not chunks[-1]['finished']:
            chunks.append(save_staged_chunk(player, 1))
        return chunks

    def test_saves_a_page_in_chunks(self):
        player = Player.objects.create(username='someone')
        chunks = self.sync(player, self.page())
        assert [chunk['done'] for chunk in chunks] == [20, 40, 45]
        assert (chunks[-1]['created'], chunks[-1]['caught_up']) == (45, False)
        assert Play.objects.filter(player=player).count() == 45
        # A finished page is dropped from the cache.
        assert save_staged_chunk(player, 1) is None

    def test_caught_up_only_when_nothing_on_the_page_changed(self):
        player = Player.objects.create(username='someone')
        self.sync(player, self.page())

        again = self.sync(player, self.page())[-1]
        assert (again['created'], again['updated'], again['caught_up']) == (0, 0, True)

        edited = self.page()
        edited[44]['quantity'] = 2
        changed = self.sync(player, edited)[-1]
        assert (changed['done'], changed['updated'], changed['caught_up']) == (45, 1, False)
        assert Play.objects.get(id=45).quantity == 2

    def test_an_empty_page_finishes_at_once(self):
        player = Player.objects.create(username='someone')
        chunks = self.sync(player, [])
        assert [(c['done'], c['finished'], c['caught_up']) for c in chunks] == [(0, True, False)]

    def test_upsert_counts_created_and_updated(self):
        player = Player.objects.create(username='someone')
        assert upsert_plays(player, self.page(3)) == {'created': 3, 'updated': 0}


class IsSellTest(SimpleTestCase):
    def game(self, idle_days: int, skipped_days_ago: int | None) -> GameScore:
        today = DAY + timedelta(days=3000)
        skipped = None if skipped_days_ago is None else today - timedelta(days=skipped_days_ago)
        return GameScore(
            1, 'Game', last_played=today - timedelta(days=idle_days), last_skipped=skipped
        )

    def test_two_years_unplayed_and_skipped_since_is_sold(self):
        assert is_sell(self.game(730, 10), DAY + timedelta(days=3000))

    def test_a_game_played_within_two_years_is_kept(self):
        assert not is_sell(self.game(729, 10), DAY + timedelta(days=3000))

    def test_a_game_not_skipped_since_its_last_play_is_kept(self):
        # Without a skip since, the player may simply have stopped logging plays.
        assert not is_sell(self.game(1000, None), DAY + timedelta(days=3000))
        assert not is_sell(self.game(1000, 1200), DAY + timedelta(days=3000))


class PriorityStarsTest(SimpleTestCase):
    def games(self, *scores: float) -> list[GameScore]:
        return [GameScore(i, f'Game {i}', score=score) for i, score in enumerate(scores)]

    def test_scales_best_to_five_and_worst_to_one(self):
        assert priority_stars(self.games(1.42, 1.22, 0.87, 0.71, 0.69)) == [5, 4, 2, 1, 1]

    def test_new_games_and_ties_get_five(self):
        assert priority_stars(self.games(math.inf, 0.9, 0.5)) == [5, 5, 1]
        assert priority_stars(self.games(0.7, 0.7)) == [5, 5]
