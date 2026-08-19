# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

South African board game buyers hunting a deal. The primary visitor already has a
specific game in mind and wants to know which local shop has it cheapest right now,
and whether that price is actually good rather than merely lowest today. They arrive
anonymously, usually from search, and leave for a shop's own site to complete the
purchase.

## Product Purpose

bggdata.co.za tracks board game prices across South African online shops, joins each
listing to its BoardGameGeek game record, and keeps the price history so a current
price can be judged against the market and against its own past. Success is a visitor
leaving for the right shop link with confidence they are not overpaying.

## Positioning

Cross-shop price history for the South African board game market, tied to BGG identity.
A single shop can show its own price; a marketplace can show today's listings. This
product knows what a game has cost across seventeen SA retailers over time, which is
what makes "cheap" a claim rather than a coincidence.

## Operating Context

- Prices are scraped per shop by dedicated scrapers in `main/shops/` (17 shop modules;
  four are currently disabled — Amazon, Meeps and Veeps, Takealot and Wizards World carry
  `enabled = 0/False`). Scrapes are logged in `Scrapelog`.
- Listings are matched to BGG games; unmatched listings carry `bgg_missing` /
  `bgg_looked_at` state.
- Daily prices are recorded per listing against a `Day`, giving each game a price series
  and a rolling average (`ROLLING_AVERAGE = 90` days).
- Visitors browse by category (Board Game, Card Game, Tabletop, RPG, Accessories, Bundle,
  Other) via `main/list.html` table views, or land on a game, listing, or shop detail page.
- The journey always terminates off-site at the shop's own product page.
- `robots.txt` disallows everything except `/` and `/games`.
- Deployed to a DigitalOcean host via the `v*` tag workflow in `.github/workflows/deploy.yml`.

## Capabilities and Constraints

- **No user accounts.** Anonymous only — no login, no saved lists, no watchlists or price
  alerts. Design must never assume a signed-in visitor or per-user state.
- **No ads, no affiliate revenue.** Outbound shop links are plain links. The Bitcoin
  address in the footer is the only ask on the site.
- **Server-rendered, no SPA.** Django templates with Bootstrap 5.3 and htmx. No React/Vue
  rewrite, no heavy client-side framework. Tables are `django-tables2`, filters are
  `django-filter`, price graphs are rendered server-side (`main/graphs.py`).
- Views are cached for 10 minutes in production (`VIEW_CACHE`), 1 second when `DEVELOPER`.
- Data is scraped and therefore imperfect: `Game.shop_outdated`, `scraped_at`, and
  `in_stock` (nullable) all exist because a shop's truth can be stale, missing, or broken.
  Out-of-stock presentation already exists in CSS (`.out-of-stock-txt`, `.out-of-stock-img`).
  The user did not commit to freshness/uncertainty messaging as a design requirement — the
  data state is fact, the treatment is open.
- Storage is SQLite, and it is large (>1GB). Query cost is a real constraint on any feature
  that wants more data on a page.
- Python 3.11+, ruff-linted at 100 columns (see CLAUDE.md).
- **Dead legacy:** the SVD recommender and player/user pages are over. `about.html`,
  `player_list.html`, `player_detail.html`, `game_sim.html`, `country*.html`, `mec.html`,
  `got.html`, `reviews.html` describe or serve that era and have no routes in `bgg/urls.py`.
  Treat them as dead weight, not as product direction.

## Brand Commitments

- Name: **BGG Data** (wordmark renders as `BGG` + lighter `Data`), domain bggdata.co.za.
- Existing identity in `main/static/main/css/main.css`: dark brown `#2a1f1a` chrome with a
  gold `#c8a45c` accent, Fraunces for display and Source Sans 3 for text, Bootstrap Icons,
  a dice-five brand mark.
- The site is unaffiliated with BoardGameGeek; it consumes BGG data and links out to it.

## Evidence on Hand

- Real, live data: seventeen shop scrapers, matched BGG game records with ratings, ranks,
  weights, player counts and play times, and a per-day price history.
- Real imagery: shop-supplied listing images and BGG game images (`Listing.img`, `Game.img`),
  referenced by URL.
- No testimonials, customer logos, press, benchmarks, partnerships, or shop endorsements
  exist. None may be invented. There is no pricing, licensing, or subscription — the site
  is free and unmonetised.

## Product Principles

1. **The cheapest link, fast.** The visitor's job ends at a shop's product page; every
   screen is judged by how directly it gets them there.
2. **History is what makes a price meaningful.** Show a number against its own past and
   against the market, never alone.
3. **Anonymous by design.** No feature may depend on identity, accounts, or stored
   per-visitor state.
4. **Server-rendered simplicity.** Reach for a template, a filter, or htmx before reaching
   for client-side machinery.
5. **Only real data.** Every game, price, shop, and rating on the site comes from a scrape
   or from BGG. Nothing is illustrative.
