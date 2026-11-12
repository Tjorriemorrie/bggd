# BGG Data

**What a game actually costs in South Africa.**

Live at **[bggdata.co.za](https://bggdata.co.za)**

BGG Data tracks board game prices across South African online shops, matches every
listing to its [BoardGameGeek](https://boardgamegeek.com) record, and records the price
every day. That history is what makes "cheap" a claim rather than a coincidence — a price
is shown against the market and against its own past, not on its own.

![The BGG Data homepage](docs/screenshot-home.png)

## What it does

- **Finds the cheapest shop today.** Every game page leads with the lowest current price,
  which shop it is at, and how far that sits below (or above) the 90-day market average.
- **Keeps the price history.** Each listing is priced daily, so a game's page shows every
  shop's line over time plus a rolling market average.
- **Covers the market.** 17 shop scrapers (13 currently live), joined to BGG identity so
  the same game across different shops is genuinely the same game.
- **Browsable by category.** Board games, card games, tabletop, RPG, accessories, bundles
  and other.
- **Sleeves by card size** (`/sleeves`). Every sleeve whose size the shop printed in its
  name. Sold-out sleeves sit at the bottom under any sort, struck through and priced at
  their last in-stock price. Entering a card's width × height ranks the sheet in the
  browser: sizes within 0.5mm on both sides first (shops print 63 and 63.5 for the same
  card), in stock then sold out; a gap; bigger sleeves in stock; then ones too small.
  Every other sold-out sleeve is hidden until the size is cleared.
- **Suggests what to play next** (`/plays`). It reads a BGG user's logged plays and, on
  every play day, counts the top 3 suggested games that weren't played as skipped. A
  game's first play day counts as one play and skips nothing, since a new game gets
  played for being new. The score combines plays vs skips with how long since each
  game was last played or skipped (see `main/plays.py`). A game is marked **Sell** once
  3 plays per played game have been logged since its last play (54 games played → 162
  plays). Waiting is counted in plays, not days, so the bar grows with the collection,
  arrives sooner for frequent players, and never trips for a player who stopped logging.
- **No accounts, no ads, no affiliate links.** It is anonymous and free, and every
  outbound shop link is a plain link.

Price history for Wingspan across fourteen shops, with the market average dashed in red:

![A game page showing the price history graph](docs/screenshot-game.png)

## How it works

Per-shop scrapers pull listings and prices, each scrape logged. Listings are matched to
BGG games (ratings, rank, weight, player counts, play time come along with the match).
Every listing gets a price recorded against a day, giving each game a price series and a
90-day rolling average. Views are cached for ten minutes and the graphs are rendered
server-side.

**Failed scrapes.** `manage.py shop <name|all>` scrapes each shop and writes a
`Scrapelog` for it: `OK`, or the error that stopped it. A request that still fails after
its retries raises, and so does a shelf whose first page holds no products (that means
the shop blocked us or changed its layout). An empty *later* page is just the end of the
shelf. `/shops` and the shop page show the last `OK` scrape date only. If any shop failed,
the command exits non-zero once every shop has had its turn. `manage.py cron` still runs
the BGG steps after a failed shop, then exits non-zero.

`main.games.get` retries 429/430/401/403/5xx responses up to 7 times (3s doubling to 60s).
So an `ERROR Too many requests …` line followed by `retrying in 3 seconds` is a retry, not
a failure: the scrape only fails if every try fails.

## Tech stack

| | |
|---|---|
| Backend | Django 5.1 on Python 3.11+ |
| Data | SQLite (>1 GB of price history) |
| Frontend | Server-rendered Django templates, Bootstrap 5.3, htmx — no SPA |
| Tables & filters | django-tables2, django-filter |
| Graphs | Plotly, rendered server-side |
| Scraping | requests, BeautifulSoup, Botasaurus |
| Hosting | DigitalOcean, deployed by GitHub Actions on a `v*` tag |

## Notes

This site is not affiliated with BoardGameGeek — it consumes BGG data and links back to
it. Prices are scraped and therefore imperfect: a shop's own site is always the final
word, which is where every link on this site ends up.
