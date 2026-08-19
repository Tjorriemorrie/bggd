---
name: BGG Data
description: Cross-shop board game price history for South Africa, printed as a hex-and-counter wargame kit.
colors:
  sheet: "#f3ecd9"
  sheet-2: "#e8dec3"
  sand: "#dece9c"
  sand-deep: "#cdb97f"
  sand-rule: "#bda76a"
  ink: "#1a1831"
  ink-2: "#55506e"
  ink-3: "#605a7c"
  crimson: "#a21232"
  crimson-deep: "#7d0d26"
  crimson-lit: "#e85f76"
  teal: "#20615b"
  teal-deep: "#164541"
  teal-lit: "#45a796"
  on-ink: "#dece9c"
  on-ink-2: "#b0a588"
  white: "#ffffff"
  wash: "rgba(222, 206, 156, 0.24)"
  wash-teal: "rgba(32, 97, 91, 0.1)"
  on-ink-hair: "rgba(222, 206, 156, 0.28)"
  on-ink-edge: "rgba(222, 206, 156, 0.4)"
  on-ink-fill: "rgba(222, 206, 156, 0.22)"
  on-ink-field: "rgba(243, 236, 217, 0.06)"
  on-ink-field-lit: "rgba(243, 236, 217, 0.12)"
  crimson-hair: "rgba(162, 18, 50, 0.35)"
  crimson-ring: "rgba(162, 18, 50, 0.28)"
  rule-hair: "rgba(26, 24, 49, 0.16)"
typography:
  display:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "clamp(1.75rem, 4.6vw, 3.25rem)"
    fontWeight: 700
    lineHeight: 1.02
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "clamp(1.5rem, 3.4vw, 2rem)"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "0.01em"
  title:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "0.04em"
  figure:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "clamp(2.75rem, 7vw, 4.25rem)"
    fontWeight: 700
    lineHeight: 0.9
    letterSpacing: "-0.03em"
    fontFeature: "tnum, lnum"
  body:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
    fontFeature: "tnum, lnum"
  label:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.16em"
  micro:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "0.5625rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.12em"
  label-xs:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "0.625rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.14em"
  label-lg:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.12em"
  body-xs:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.4
  body-sm:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.45
  body-lg:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  title-lg:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.12
  title-xl:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 700
    lineHeight: 1.1
  figure-sm:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 700
    lineHeight: 1
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Cascadia Mono, Menlo, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.4
  detail-title:
    fontFamily: "Archivo Narrow, Arial Narrow, Helvetica Neue, system-ui, sans-serif"
    fontSize: "clamp(1.625rem, 3.6vw, 2.375rem)"
    fontWeight: 700
    lineHeight: 1.12
rounded:
  cut: "2px"
spacing:
  s1: "4px"
  s2: "8px"
  s3: "12px"
  s4: "16px"
  s5: "24px"
  s6: "32px"
  s7: "48px"
  s8: "64px"
  s9: "96px"
components:
  commit:
    backgroundColor: "{colors.crimson}"
    textColor: "#ffffff"
    typography: "{typography.label}"
    rounded: "{rounded.cut}"
    padding: "12px 24px"
  commit-hover:
    backgroundColor: "{colors.crimson-deep}"
    textColor: "#ffffff"
  ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.cut}"
    padding: "8px 12px"
  ghost-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sand}"
  counter:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.cut}"
  verdict:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink}"
    rounded: "{rounded.cut}"
    padding: "24px"
  filter-input:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.cut}"
    padding: "8px 12px"
    height: "40px"
  roster-header:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink-2}"
    typography: "{typography.label}"
    padding: "12px"
---

# Design System: BGG Data

## Overview

**Creative North Star: "The Counter Sheet"**

BGG Data is printed, not rendered. Its world is the Avalon Hill / SPI hex-and-counter
wargame kit: buff map stock, die-cut cardboard counters carrying their factors in flat
spot ink, and a cross-reference chart you consult to answer one question. The product's
question is "is this price good?", and a wargame's answer to any question is a table
lookup, so that is the form the whole site takes.

The system is dense and ruled rather than airy and floating. Structure is carried by
hairlines and ink rules, not by cards drifting on shadows; the single elevation in the
system exists because a counter physically lies on top of the sheet. Numbers are the
subject matter, so every figure is set in tabular lining figures and every price column
is right-aligned against its neighbours. Colour is spot ink applied sparingly: crimson
means commit, teal means below-average or in stock, and everything else is paper and
print.

The deliberate anti-reference is the price-comparison SaaS page: the equal-weight card
grid, the green savings pill, the rounded floating panel. Nothing here is soft.

**Key Characteristics:**
- Buff paper ground with a faint printed fibre tooth, never flat white
- Ruled structure; 2px die-cut corners; no rounded surfaces
- One accent for action (crimson), one for advantage (teal)
- Condensed display face over a neutral text face, tabular figures throughout
- Every sheet reports its own scope: a title on the left, a real fact on the right

## Colors

A four-ink palette printed on buff stock: two paper tones, one dark ink, and two spot
colours that each mean exactly one thing.

### Primary
- **Commit Crimson** (`#a21232`): the one action colour. It appears on the primary
  outbound button, on above-average deltas, on the out-of-stock mark, on links, on the
  focus ring, and on the hairline under the navigation. It appears on nothing that is
  not an action or a warning.
- **Crimson Deep** (`#7d0d26`): pressed and hovered state of the commit key.
- **Crimson Lit** (`#e85f76`): the same signal read on the ink ground, where the base
  crimson would not carry.

### Secondary
- **Chart Teal** (`#20615b`): advantage. Below the market average, in stock, the boxed
  cheapest quote, a shop's own price series.
- **Teal Deep** (`#164541`) and **Teal Lit** (`#45a796`): the same signal on the boxed
  best row and on the ink ground respectively.

### Neutral
- **Map Stock** (`#f3ecd9`): the page ground, carried with a repeating-gradient fibre
  tooth so it reads as paper rather than as a fill.
- **Stock Shade** (`#e8dec3`): zebra rows and the scroll track.
- **Sand Field** (`#dece9c`): the pinned map field. Counter art beds, chart cells, the
  printed prefix on the search instrument, and every surface set into the sheet.
- **Sand Deep** (`#cdb97f`) and **Sand Rule** (`#bda76a`): the ruled hairlines between
  sand surfaces.
- **Print Ink** (`#1a1831`): body text, the chrome, the verdict band, table headers.
- **Ink Mid** (`#55506e`): secondary text and small caps labels. This is the lightest
  ink allowed to carry content.
- **Ink Faint** (`#605a7c`): decorative marks only, such as the breadcrumb slash and the
  scrollbar thumb at rest.
- **On Ink** (`#dece9c`) and **On Ink Mid** (`#b0a588`): type set on the ink ground.

### Named Rules
**The One Commit Rule.** Crimson is filled only on the thing the visitor came to press:
the link out to the shop. A second filled crimson button on the same sheet is a bug.

**The Faint Ink Rule.** `ink-3` never carries a word the visitor needs. Every label,
price and name reads at 4.5:1 or better on whichever paper tone is behind it, which
means content text stops at `ink-2`.

## Typography

**Display Font:** Archivo Narrow (fallback Arial Narrow, Helvetica Neue, system-ui)
**Body Font:** Archivo (fallback system-ui, -apple-system, Segoe UI)
**Mono:** the platform monospace stack, used for exactly one thing: the Bitcoin address
in the footer, which is a string to be copied character by character. Monospace is never
a costume for "technical" here.

**Character:** A condensed grotesque over its normal-width sibling. The narrow face is
the chart header and the counter print: it compresses long shop names and game titles
into fixed columns without shrinking them. The regular face carries prose. Both are
loaded with tabular lining figures, because the site is a table of numbers.

### Hierarchy
- **Display** (700, `clamp(1.75rem, 4.6vw, 3.25rem)`, 1.02, uppercase): the home
  masthead only.
- **Headline** (700, `clamp(1.5rem, 3.4vw, 2rem)`, 1.12, uppercase): the sheet title, be
  it a game, a listing, a shop, or a category roster.
- **Title** (700, `1.125rem`, uppercase, `0.04em`): section rules inside a sheet.
- **Figure** (700, `clamp(2.75rem, 7vw, 4.25rem)`, 0.9, `-0.03em`): the price in the
  verdict band. Nothing else is set at this scale.
- **Body** (400, `0.9375rem`, 1.55): prose, capped at `--measure` (68ch); the game
  description sets in two columns above 1000px.
- **Label** (700, `0.6875rem`, `0.16em`, uppercase): every small caps legend, including
  column headers, scope notes, factor names, breadcrumbs and chips.

### Named Rules
**The Tabular Rule.** `font-variant-numeric: tabular-nums lining-nums` is set on the
body and inherited everywhere. Prices in a column line up on the digit, always.

**The Scope Rule.** A heading is never preceded by a kicker. Where a section needs
context it gets a scope note on the same rule, right-aligned, in the label style:
"28 listings", "furthest below their market average", "from BoardGameGeek".

## Layout

A single centred column, `--page: 1440px` wide, with a fluid gutter of
`clamp(16px, 4vw, 40px)`. Spacing is an eight-step scale from 4px to 96px; sections are
separated by `--s8` (64px) and grouped internally at `--s3` and `--s4`.

Breakpoints are one ladder, used everywhere:

| Step | max-width | What changes |
|---|---|---|
| sm | 559.98px | Counter trays drop to two columns; the roster sheds its low-priority columns; the home key stacks to one track |
| md | 619.98px | Section titles and their scope notes stack; trays and cross-reference rows tighten |
| lg | 859.98px | Detail sheets go single-column; the verdict band stacks; rosters shed mid columns |
| xl | 999.98px | The navigation rail collapses behind the toggle; the description drops from two columns to one |

Price charts are the one place where the server cannot know the width, so the chart box
is sized in CSS per step from three custom properties the view computes from the number
of entries the chart's key has to print.

## Elevation & Depth

Depth is structural, not atmospheric. Almost everything is defined by a rule: a 1px sand
hairline between cells, a 1px ink rule around a component, a 2px ink rule under a
heading. There is exactly one shadow in the system, and it exists because a counter
physically lies on the sheet.

### Shadow Vocabulary
- **Lift** (`box-shadow: 0 1px 2px rgba(26,24,49,0.14), 0 6px 14px rgba(26,24,49,0.11)`):
  the resting state of the commit key and the detail counter.
- **Lift High** (`box-shadow: 0 2px 4px rgba(26,24,49,0.16), 0 14px 28px rgba(26,24,49,0.16)`):
  hover on a counter tile or the commit key, paired with a 2-3px rise.

### Named Rules
**The Ruled-Not-Floated Rule.** A new surface earns a rule, not a shadow. If a component
needs separating from the sheet it gets `--rule-ink`; a shadow is reserved for the two
things meant to read as lying on top of the paper.

## Shapes

Cardboard is not rounded. Every corner in the system is `--r-cut: 2px`, a die-cut corner
rather than a radius. Borders come in four weights: `--rule-hair` (translucent ink),
`--rule` (sand), `--rule-ink` (1px ink) and `--rule-heavy` (2px ink, reserved for the
rule under a sheet title or section title). Missing cover art is not a hole in the
sheet: it prints as a 45-degree hatch with a small caps caption, and a cover URL that
stops resolving falls back to the same printed blank.

## Components

### Buttons
- **Shape:** 2px die-cut corners (`--r-cut`).
- **Commit (primary):** crimson fill, white uppercase label at `0.1em`, `12px 24px`
  padding, resting `--lift`. Hover deepens to `--crimson-deep`, rises 2px and takes
  `--lift-high`. Active returns to rest.
- **Ghost (secondary):** no fill, 1px ink rule, ink label. Hover inverts to ink fill with
  sand text. `aria-pressed="true"` holds the inverted state, which is how the chart's
  period toggle reads.
- **Focus:** every focusable element takes a 2px crimson outline at 2px offset.

### Counter (signature component)
The tray tile, and the product's mark. A 1px ink rule around a sand art bed, the title
and price printed below in fixed positions, and an ink footer strip carrying the shop.
The factor chip, a saving percentage or an out-of-stock flag, sits top-right on the art.
Positions are identical at every size, so the tile is learned once and read everywhere.
Hover rises 3px onto `--lift-high`.

### Verdict band (signature component)
The answer to "is this price good?", and the loudest thing on any detail sheet. An ink
band carrying up to three bays: the price at figure scale in sand; the delta against the
90-day average in teal-lit (below) or crimson-lit (above) with its plain-language label;
and the commit key aligned right. A band with only one bay to report takes
`.verdict-solo` and tightens rather than leaving empty bays.

### Cross-reference table (signature component)
Every shop's quote for one game, ruled into rows of art, shop, listing name and price,
with the cheapest in-stock row boxed in a 2px teal outline. Its two rosters, in stock and
out of stock, are tabs, and the sheet opens on whichever one has rows.

### Roster (data table)
An ink header in label type with sand column rules, sand zebra body rows, and a full sand
row on hover. Cells carry `roster-num` (right-aligned figures), `roster-price` (display
face) or `roster-mark` (centred boolean). Column headers are sort links with a 24px
minimum target and a caret in the active direction.

### Inputs / Fields
The search instrument is one ruled box: a sand prefix panel printing what the field
searches, the field itself, and an ink submit key that turns crimson on hover. Focus
lights the whole instrument with a crimson ring via `:focus-within`, not just the input.
An active search prints as a sand chip beside the instrument with a clear key.

### Marks
Boolean data is a drawn Bootstrap icon in teal (yes) or crimson (no) at a 24px target,
always paired with a screen-reader name and a title. Colour carries the mood; the glyph
and its name carry the fact.

### Navigation
A sticky ink chrome with a crimson hairline beneath it: brand and search on the top row,
a rail of sections below. Sections are label type; the current one takes sand with a
crimson underline. Below 1000px the rail collapses behind a three-bar toggle.

### Empty states
A ruled sand panel with a title, one sentence explaining why it is empty in the product's
own terms, and the routes out: a commit key to clear the search and a ghost key back to
the full sheet.

## Do's and Don'ts

### Do:
- **Do** rule a new surface with `--rule-ink` and give it `--r-cut` corners.
- **Do** set every number in the display face with tabular figures, right-aligned in its
  column.
- **Do** put a real fact in the scope slot of a section rule: a count, a period, a source.
- **Do** pair every colour-coded mark with a screen-reader name.
- **Do** state an empty or missing state in the sheet's own language, with a route out.
- **Do** size a chart's box from what its key has to print, per breakpoint step.

### Don't:
- **Don't** round a corner past 2px, or reach for a shadow where a rule will do.
- **Don't** fill crimson on anything that is not the visitor's commit.
- **Don't** set content text in `ink-3`, or any label under 4.5:1 on its ground.
- **Don't** put a kicker or an eyebrow above a heading.
- **Don't** encode a fact in colour alone.
- **Don't** print a currency prefix on a signed movement series without its zero rule.
