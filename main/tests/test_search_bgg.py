from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from main.games import URL_SEARCH, URL_THING, clean_listing_name, search_bgg


def _xml(*games: tuple[str, str, int]) -> bytes:
    """BGG XML API2 items for (id, name, usersrated) games."""
    items = ''.join(
        f'<item type="boardgame" id="{bgg_id}"><name type="primary" value="{name}"/>'
        f'<statistics><ratings><usersrated value="{rated}"/></ratings></statistics></item>'
        for bgg_id, name, rated in games
    )
    return f'<?xml version="1.0" encoding="utf-8"?><items>{items}</items>'.encode()


class FakeBgg:
    """Answers exact and loose searches from a list of games, like BGG's XML API2 does."""

    def __init__(self, *games: tuple[str, str, int]):
        """Serve these (id, name, usersrated) games."""
        self.games = games
        self.queries = []

    def get(self, url, params=None, headers=None, redirect=False):
        if url == URL_THING:
            ids = params['id'].split(',')
            return SimpleNamespace(content=_xml(*(g for g in self.games if g[0] in ids)))
        assert url == URL_SEARCH
        query = params['query'].lower()
        self.queries.append((query, 'exact' in params))
        if 'exact' in params:
            hits = [g for g in self.games if g[1].lower() == query]
        else:  # every word somewhere in the name, results in alphabetical order
            hits = sorted(
                (g for g in self.games if all(w in g[1].lower() for w in query.split())),
                key=lambda g: g[1],
            )
        return SimpleNamespace(content=_xml(*hits))


class CleanListingNameTests(SimpleTestCase):
    def test_strips_shop_notes(self):
        cases = {
            'Stellar (Pre-Loved) Sleeved': 'Stellar',
            'Targi BUNDLE (Pre-loved)': 'Targi',
            'Kingdomino: Age of Giants Expansion (Pre-loved)': 'Kingdomino: Age of Giants',
            'Concordia - Gallia / Corsica (In Stock with supplier - 5 to 10 days delivery)': (
                'Concordia: Gallia / Corsica'
            ),
            'Arkham Horror LCG | The Boundary Beyond': 'Arkham Horror LCG: The Boundary Beyond',
        }
        for name, clean in cases.items():
            with self.subTest(name=name):
                assert clean_listing_name(name) == clean

    def test_keeps_bgg_punctuation_and_fixes_mojibake(self):
        mojibake = 'Harry Potter: Hogwarts Battle â€“ The Charms and Potions'
        fixed = 'Harry Potter: Hogwarts Battle – The Charms and Potions'
        assert clean_listing_name(mojibake) == fixed
        assert clean_listing_name('Yamataï') == 'Yamataï'


class SearchBggTests(SimpleTestCase):
    def search(self, bgg: FakeBgg, name: str) -> dict:
        with patch('main.games.get', bgg.get):
            return search_bgg(name)

    def test_alphabetical_first_loose_result_is_not_a_match(self):
        bgg = FakeBgg(('1', 'Galaxy Defenders', 900), ('2', 'Galaxy Trucker', 5000))
        assert self.search(bgg, 'Galaxy Hunters')['bgg_id'] is None
        assert bgg.queries[-1] == ('galaxy', False)

    def test_exact_name_shared_by_two_games_goes_to_the_most_rated(self):
        bgg = FakeBgg(('107448', 'Sagrada', 40), ('199561', 'Sagrada', 60000))
        assert self.search(bgg, 'Sagrada (Pre-loved)')['bgg_id'] == '199561'

    def test_loose_search_drops_trailing_words_and_scores_the_rest(self):
        bgg = FakeBgg(
            ('1', 'Marvel Champions: The Card Game', 50000),
            ('2', 'Marvel Champions: The Card Game – NeXt Evolution', 3000),
            ('3', 'Marvel Champions: The Card Game – Mutant Genesis', 4000),
        )
        result = self.search(bgg, 'Marvel Champions LCG - NeXt Evolution Expansion Box')
        assert result['bgg_id'] == '2'
        assert ('marvel champions next evolution', False) in bgg.queries

    def test_edition_qualifier_picks_the_edition_but_does_not_rule_out_a_match(self):
        bgg = FakeBgg(('1', 'Pax Pamir', 9000), ('2', 'Pax Pamir: Second Edition', 20000))
        assert self.search(bgg, 'Pax Pamir (2nd Edition)')['bgg_id'] == '2'
        bgg = FakeBgg(('13', 'CATAN', 120000), ('5', 'CATAN: Seafarers', 30000))
        assert self.search(bgg, 'Catan (6th Edition)')['bgg_id'] == '13'

    def test_accessory_of_a_game_is_not_the_game(self):
        bgg = FakeBgg(('1', 'Wyrmspan', 20000), ('2', 'Wyrmspan: Dragon Guild', 900))
        assert self.search(bgg, 'Wyrmspan – Natural Rubber Playmat')['bgg_id'] is None
