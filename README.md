# BGG Data

**What a game actually costs in South Africa.**

Live at **[bggdata.co.za](https://bggdata.co.za)**

BGG Data tracks board game prices across South African online shops, matches each listing
to its [BoardGameGeek](https://boardgamegeek.com) record and records the price daily, so
"cheap" is a claim, not a coincidence: a price is shown against the market and its past.

![The BGG Data homepage](docs/screenshot-home.png)

## What it does

- **Finds the cheapest shop today.** Every game page leads with the lowest current price,
  which shop it is at, and how far that sits below (or above) the 90-day market average.
- **Keeps the price history.** Each listing is priced daily, so a game's page shows every
  shop's line over time plus a rolling market average.
- **Covers the market.** 17 shop scrapers (14 currently live), joined to BGG identity so
  the same game across shops is the same game. Browsable by category: board games, card
  games, tabletop, RPG, accessories, bundles and other.
- **Sleeves by card size** (`/sleeves`). Every sleeve whose size the shop printed in its
  name. Sold-out sleeves sit at the bottom under any sort, struck through, at their last
  in-stock price. A card's width × height ranks the sheet in the browser: sizes within
  0.5mm on both sides first (shops print 63 and 63.5 for one card), in stock then sold out;
  a gap; bigger sleeves in stock; then too small. Other sold-out sleeves hide until cleared.
- **Suggests what to play next** (`/plays`). It reads a BGG user's logged plays and, on
  every play day, counts the top 3 suggested games that weren't played as skipped. A game's
  first play day counts as one play and skips nothing (a new game gets played for being
  new). The score combines plays vs skips with how long since each game was last played or
  skipped (see `main/plays.py`). A game is marked **Sell** once 3 plays per played game
  have been logged since its last play (54 games played → 162 plays). Counted in plays, not
  days, the bar grows with the collection, comes sooner for frequent players, and never
  trips for a player who stopped logging.
- **No accounts, no ads, no affiliate links.** It is anonymous and free, and every
  outbound shop link is a plain link.

Price history for Wingspan across fourteen shops, with the market average dashed in red:

![A game page showing the price history graph](docs/screenshot-game.png)

## How it works

Per-shop scrapers pull listings and prices, each scrape logged. `game auto` matches new
listings to BGG games (bringing ratings, rank, weight, player counts, play time): an exact
name search, else a loose one scored on shared words; ties go to the most rated game, and a
score under 0.7 leaves the listing for the admin lookup ([details](docs/bgg-matching.md)).
Every listing gets a price per day, giving each game a price series and a 90-day rolling
average. Views are cached for ten minutes; graphs are rendered server-side.

**Failed scrapes.** `manage.py shop <name|all|home>` writes a `Scrapelog` per shop: `OK`, or
the error that stopped it. A request still failing after its retries raises, as does a shelf
whose first page holds no products (blocked, or the layout changed); an empty *later* page
ends the shelf. `/shops` and the shop page show the last `OK` date only. If any shop failed,
the command (and `manage.py cron`, after its BGG steps) exits non-zero once all have run.

`main.games.get` retries 429/430/401/403/5xx responses and connection errors up to 7 times
(3s doubling to 60s). So an `ERROR Too many requests …` line followed by `retrying in 3
seconds` is a retry, not a failure. With `redirect=True` a redirect to another host raises
`OffsiteRedirectError` at once, unretried. Every error carries a message (e.g. `Blocked
(HTTP 403): <url>`), and that message is the `Scrapelog` outcome.

**Timeless** is read from its shop sheet alone (`/online-shop/?category=…&page=…`, 27 cards
a page, ~50 pages of board games); on a sale card a `<strike>` holds the old price first.
Sold-out products are left off the sheet (since 2026-11-17), so `missed_listings` marks them
out of stock. On 2026-11-17 the sheet briefly had no prices (product pages did); back that day.

**Blocked shops** (checked 2026-11-17). The droplet (DigitalOcean, NL, UTC) runs `manage.py
cron` at 12:00 UTC from its crontab, not this repo; shops take ~20 min, the BGG steps hours.
**The Geek Home** redirected the old 03:00 UTC run to `https://127.0.0.1/` (a WordPress
security plugin) but answers at 12:28; `scrape_first = True` puts it first in `shop all`.
**The Hidden Den** and **Pwned Games** 403 the droplet, 200 a home Vodacom IP. Via PIA's
`south-africa` region (AS212238 Datacamp, JNB) Hidden Den 200s, Pwned gives Cloudflare's hard
"Sorry, you have been blocked" (WAF rule, no JS challenge). Pwned also 403s curl's User-Agent.

**Scraped from home.** `shop all` skips `via_home = True` shops (those two). The laptop task
"bggd home scrape" (13:00 SAST = 11:00 UTC, or on wake if missed; logged-on only, as S4U
needs admin) runs `%LOCALAPPDATA%\bggd\home-scrape.cmd` under `conhost --headless`: `ssh -R
1080 bgg@<droplet> "… ALL_PROXY=socks5h://127.0.0.1:1080 … shop home"` (a SOCKS proxy on the
droplet's localhost, exiting from the laptop; `requests` honours `ALL_PROXY`), output in
`home-scrape.log` beside it. PIA's split tunnel lets `C:\Windows\System32\OpenSSH\ssh.exe`
bypass the VPN. Both shops took ~17 min on 2026-11-17. **Bare-IP requests** (scanners probing
`/.env`, `/.git/config`, ~100 a day, logged as `Invalid HTTP_HOST header`) get nginx's 444 via
`deploy/nginx/geoip2-block.conf`: only `(www.)bggdata.co.za` is served. Commands skip ALLOWED_HOSTS.

## Tech stack

| | |
|---|---|
| Backend | Django 5.1 on Python 3.11+ |
| Data | SQLite (>1 GB of price history) |
| Frontend | Server-rendered Django templates, Bootstrap 5.3, htmx — no SPA |
| Tables, filters, graphs | django-tables2, django-filter; Plotly, rendered server-side |
| Scraping | requests, BeautifulSoup, Botasaurus |
| Hosting | DigitalOcean, deployed by GitHub Actions on a `v*` tag |

## Notes

Not affiliated with BoardGameGeek: it consumes BGG data and links back. Prices are scraped,
so imperfect: a shop's own site, where every link here ends up, is the final word.
