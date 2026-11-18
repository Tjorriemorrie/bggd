# Matching listings to BGG games

`main.games.search_bgg(name)` finds the BGG game a shop listing stands for. `manage.py game
auto` (run by `cron`) calls it for every listing with no `bgg_id` that is not `bgg_missing`,
and the admin lookup (`/admin/main/listing/lookup/`) shows its answer as the suggestion.

## How it matches

1. `clean_listing_name` drops shop notes: `(Pre-loved)`, `(Pre-owned)`, `SLEEVED`, `SEALED`,
   `BUNDLE`, `(Ready to Ship)`, `(In Stock with supplier …)`, a trailing `Expansion`/`Exp`.
   It fixes mojibake (`â€“` → `–`) and turns a spaced hyphen or bar into a colon. En dashes
   stay, because BGG writes `Game: Sub – Expansion`.
2. An **exact** search on the cleaned name wins outright.
3. Otherwise a **loose** search runs on the name's words, dropping trailing words until BGG
   returns something, down to half the words. Every result is scored with the Dice overlap of
   the words (lowercase ascii; `&` = `and`; `'` and `.` join words; stopwords dropped:
   a, an, and, of, the, to, game, board, edition, expansion, exp). `LCG` scores as `card`.
4. **Qualifiers** pick an edition but never rule a game out: words in `()`/`[]`, the word
   before `Edition`, and digit ordinals (`2nd` scores as `second`). So `Pax Pamir (2nd
   Edition)` picks *Pax Pamir: Second Edition*, and `Catan (6th Edition)` still finds *CATAN*.
5. A best score under `MATCH_MIN_SCORE` (0.7) is `not_found`, so the listing waits for review.
   A tie (exact or scored) goes to the game with most BGG ratings (one `thing` call).

## BGG XML API2 findings (2026-11-18)

- Search: `https://boardgamegeek.com/xmlapi2/search?type=boardgame&query=…[&exact=1]` with
  `Authorization: Bearer <BGG_AUTH>`. `type=boardgame` returns expansions too. Each item has
  only id, one name (primary or the alternate that matched) and year: no ratings.
- `exact=1` ignores case but not punctuation or accents: `brass: birmingham` hits,
  `Brass Birmingham` and `Yamatai` (for *Yamataï*) don't. It matches alternate names too.
- Loose search ANDs the words as substrings (`Small World` finds *Famous Fairways: The World's
  Smallest Golf Game*) and ignores punctuation. Results are **alphabetical**, so the first is
  arbitrary.
- Different games can share a name exactly: `Sagrada` returns the 2007 and the 2017 game.
- `thing?id=a,b,…&stats=1` takes up to 20 ids; `usersrated` is the rating count.
- BGG throttles bursts: a long run of searches averaged ~6s a request through 429 retries.

## Why it changed (local DB copy, 2026-11-18)

The old matcher took `items[0]` of the loose search and then retried with the first and last
words cut off, so it nearly always "found" something. About 2,160 of 26,200 matched non-BGBSA
listings (~8%) were linked to a game sharing under half its name. Dice sets, TCG boosters,
LEGO sets and X-Wing ships piled onto *1000 Blank White Cards* (43 listings), *Jetzt
schlägt's 18!* (39) and *'65: Action Card Expansion 2nd Edition* (38). `bgg_looked_at` is no
proof of review: 1,133 listings got it in one minute on 2024-12-08.

Offline check against the DB: the new scorer accepts 92% of confirmed matches (listing and
BGG name share at least half the words) and rejects 96% of the junk pairs. Most of the
confirmed matches it rejects are variant-to-base calls a reviewer made at 0.67 (`Squadro Mini`
→ *Squadro*, `Spot it! Harry Potter` → *Spot it!*), plus LEGO and accessory products.

## Known limits

- An accessory named after a multi-word game still matches the game: `Lost Ruins of Arnak
  Playmat` scores 0.86 against *Lost Ruins of Arnak*.
- Words BGG writes with dots or accents aren't found by the loose search (`Time Stories` for
  *T.I.M.E Stories*, `Yamatai`), though they score fine once found.
- `bgg_missing` listings are never searched again, even ones the new matcher would find.
