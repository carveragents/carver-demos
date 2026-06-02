# Trader Dashboard — Design Spec

## Overview

A Carver-enhanced trader dashboard for prediction market participants. Unlike the existing Pred-Oracle demos (which target platform operators — GC, Head of Listing, Head of International), this demo answers the trader's question: **"What does the regulatory record say about the contracts I hold?"**

The demo is a static site (same architecture as the existing Pred-Oracle demos) with pre-rendered pages built from the Carver corpus + LLM enrichments + real probability data from Kalshi/Polymarket APIs.

### Target personas

- **Retail bettor** — wants plain-English "what's happening with my contract"
- **Sophisticated retail** — wants structured regulatory intelligence to inform positioning
- **Market maker / prop desk** — wants quantitative signals and structured data

The demo is designed to resonate across all three; the contract briefing page scales from casual scanning (direction badges, narrative) to deep research (full timeline, thesis tracker, regulatory references).

### Data latency assumption

Same-day (1-24h) from regulator publication to visibility. This is not a trading signal product — it's an informed-positioning tool. The value prop is "understand the regulatory forces shaping your contracts" not "trade faster."

---

## Demo Structure

```
trader/
  index.html                          — Portfolio list view (default)
  calendar/index.html                 — Portfolio calendar view
  contracts/{id}/index.html           — Contract briefing (6 contracts)
  retrospectives/index.html           — Case studies landing
  retrospectives/{id}/index.html      — Retrospective briefing (2 contracts)
```

Four parts, three in the trader workflow + one standalone:

```
Portfolio Dashboard
  ├── List View  ◄─toggle─►  Calendar View
  └── click contract ──────► Contract Briefing

Retrospective Case Studies (standalone)
  ├── Solana ETF (resolved YES)
  └── TikTok Ban (resolved YES)
```

---

## Part 1: Portfolio List View

**Route:** `trader/index.html`

The trader's home screen. One row per contract, dense with signal. Header shows "Alex's Portfolio" (light persona — the trader is the viewer, not a character).

### Row layout

Each row contains:

| Element | Source | Notes |
|---|---|---|
| Heat tier badge | `_heat_panel.py` | Color-coded chip: dormant (gray) / watch (amber) / active (orange) / critical (red) |
| Contract title | contract YAML | Truncated with platform chip (Kalshi green / Polymarket blue) |
| Price display | platform API (cached) | Kalshi format: "YES 62c / NO 38c" with payout "$100 -> $161" |
| Net direction | new enrichment (aggregated) | Arrow + label: "Bullish" / "Bearish" / "Mixed" — majority direction of recent events |
| Regulatory momentum | `_heat_panel.py` | Heat value + 7d delta with arrow (up 18.3 / down 4.1) |
| Event count | entity match | "12 events (90d)" |
| Next catalyst | date fields | Nearest future effective_date or comment_deadline with countdown ("in 14d"). Blank if none |
| Latest event line | enriched timeline | Date + title snippet + direction badge + magnitude |

### Sort and filter

**Sort options (dropdown, single-select):**
- Heat score (default, descending)
- Next catalyst (soonest first, nulls last)
- 7d delta (biggest movers first)
- Latest event (most recent first)

**Filter options:**
- Platform: All (default) / Kalshi / Polymarket
- Heat tier: All (default) / Critical / Active / Watch / Dormant
- Has upcoming catalyst: All (default) / Yes / No

For the demo, sort and filter are functional JavaScript — the data is small enough (6 rows) to filter client-side without a build step per combination.

### Position data

Each contract row shows a synthetic trading position ("200 YES @ $0.54"). This is demo data and gets a small "demo" badge. The positions are hand-curated in a YAML file to create variety (some YES positions, some NO, varied sizes).

---

## Part 2: Portfolio Calendar View

**Route:** `trader/calendar/index.html`

Toggle from list view (shared nav toggle). Monthly calendar grid showing the same 6 contracts oriented around dates.

### Date markers

Each date cell can contain colored markers:

| Marker | Color | Source |
|---|---|---|
| High-impact regulatory event | Red dot | Events with `high_impact: true` from relevance enrichment |
| Medium-impact regulatory event | Amber dot | `relevance_score >= 5` and not high_impact |
| Contract settlement/expiration | Blue marker | `resolved_at` or settlement date from contract YAML |
| Comment deadline | Green marker | `comment_deadline` field from Carver annotation |
| Effective date (rule goes live) | Purple marker | `effective_date` field from Carver annotation |

### Interactions

- **Hover** on a date marker — tooltip with event title + which contract(s) it touches
- **Click** a date — expanded panel below calendar showing full event details for that day
- **Contract chips** next to relevant markers — clicking navigates to that contract's briefing page
- **Month navigation** — prev/next. Demo pre-renders the current month + one month forward and one month back (3 months total)

### Catalyst density

Weeks with 3+ markers get a subtle background highlight and a "busy week" label. This is the "heads up, pay attention" signal for traders managing multiple positions.

### Regulatory event ticker

A scrolling strip below the calendar showing the 5 most recent regulatory events across all portfolio contracts. Each entry shows: date, contract chip, event title, direction badge. Clicking navigates to the contract briefing.

### Data coverage note

Only ~27% of Carver records have `effective_date` and ~8% have `comment_deadline`. The calendar will be sparse for some contracts. This is honest — we show what exists. A small footnote on the page explains: "Dates shown are from official regulatory filings. Not all regulatory actions have announced future dates."

---

## Part 3: Contract Briefing

**Route:** `trader/contracts/{id}/index.html` (6 pages)

The deepest layer. Reached by clicking any contract row (list view) or contract chip (calendar view). Full regulatory intelligence for one contract.

### Above the fold — platform-native header

The top of the page echoes the Kalshi/Polymarket contract card format so the trader sees something familiar:

**Header block:**
- Contract title + platform chip + heat tier badge
- Settlement/expiration date
- Price buttons: "YES 62c" / "NO 38c" with payout math
- Synthetic position display with demo badge

**Probability chart with regulatory overlay:**
- X-axis: time (contract life, from `listed_at` to now or `resolved_at`)
- Y-axis: probability (0-100%)
- Line: real probability data from platform API (cached)
- Vertical markers at each relevant regulatory event's `pub_date`:
  - Green line = bullish event
  - Red line = bearish event
  - Gray line = neutral event
  - Marker height varies by magnitude (high = full height, medium = 2/3, low = 1/3)
- Hover on marker reveals: event title, direction, magnitude, one-line-why
- Click marker scrolls to that event in the timeline below

**Data source:** Real probability data from Kalshi (`/historical/markets/{ticker}/candlesticks` for resolved, `/series/{ticker}/markets/{ticker}/candlesticks` for active) or Polymarket (`/prices-history`). Cached in `build/_cache/prices/` as JSON, committed to git.

### Below the fold — Carver intelligence

**Left column (primary, ~65% width):**

#### 1. Thesis tracker

LLM-decomposed conditions (A/B/C) from existing `_thesis.py`. Each condition shows:
- Condition ID (A/B/C) with colored dot
- Label (<=40 chars) + summary (<=200 chars)
- Progress bar: ratio of bullish vs bearish events tagged to this condition
  - Green fill = bullish events, red fill = bearish events, gray = neutral
  - e.g., 7 bullish / 2 bearish / 3 neutral = mostly green bar
- Count: "7 bullish, 2 bearish, 3 neutral"
- Most recent event touching this condition (date + title snippet)

#### 2. Regulatory timeline

Vertical timeline of all relevant events (up to 20, from existing enrichment pipeline). Each event shows:

- **Date** + regulator name
- **Event title** (linked to source URL via `metadata.feed_url`)
- **Direction badge**: Bullish / Bearish / Neutral (green / red / gray chip)
- **Magnitude badge**: High / Medium / Low (filled / half-filled / outline variant)
- **Mechanism label**: Binding Action / Signal / Context (text label, not a badge — keeps visual noise down)
- **Timeline shift indicator**: Sooner / Later (only shown when not "none" — a small clock icon with arrow, to avoid cluttering events where timing isn't affected)
- **Condition tag**: colored dot matching thesis tracker (A = blue, B = orange, C = purple, background = gray)
- **One-line-why**: the LLM-generated 160-char explanation

Events are ordered chronologically (newest first).

#### 3. Narrative summary

2-3 sentence storyline from existing `_narrative.py`. Displayed as a card below the timeline.

**Right column (sidebar, ~35% width):**

#### 4. Regulatory momentum panel

From existing `_heat_panel.py`:
- Heat value + tier badge
- 7d delta with directional arrow
- Peer percentile ("hotter than 82% of tracked contracts")
- 14-day urgency-weighted sparkline
- Primary drivers (1-3 short strings)
- Heat explainer (1 sentence)

#### 5. Upcoming catalysts

List of future-dated events extracted from the enriched timeline:
- Events with `effective_date` or `comment_deadline` in the future
- Each shows: date, countdown ("in 14d"), event title, expected direction + magnitude
- Sorted by date (soonest first)
- If no upcoming catalysts, shows "No upcoming regulatory dates on record"

---

## Part 4: Retrospective Case Studies

**Routes:**
- `trader/retrospectives/index.html` — landing with cards for each case study
- `trader/retrospectives/{id}/index.html` — 2 pages

Accessible from a "Case Studies" nav link. Not part of the portfolio workflow.

### Two case studies

1. **Solana ETF** (Polymarket, resolved YES, Dec 2025) — 20 events over 18 months. SEC moved from resistance to approval. Condition A (NYSE Arca) accumulated bullish signals months before resolution.

2. **TikTok Ban** (Kalshi, resolved, Apr 2025) — FCC/CFIUS/Congress actions tracing the ban timeline. Binary political/regulatory event with clear milestones.

### Layout

Same as contract briefing (Part 3) with two additions:
- **Resolution banner** at top: "Resolved YES on Dec 15, 2025" (green) or appropriate outcome
- **Probability chart** shows the full arc from listing to resolution with regulatory event markers — the visual proof that regulatory signals preceded price moves

### Framing

NOT "you would have made money." Instead: "Here's what the regulatory record showed, when it showed it, and how it mapped to resolution conditions. The same system is running on your live contracts now."

Each retrospective reuses the existing enriched timeline data from the gamma demo (solana-etf-2025, tiktokban-25apr30 are already fully enriched with thesis, relevance, heat, and narrative). The only new enrichment needed is the directional impact fields (direction, magnitude, timeline_shift) which are added to the relevance schema.

---

## New Enrichment: Directional Impact

### Schema extension

The existing `_relevance.py` output schema is extended with three new fields. This is a single LLM call per event (same call as existing relevance judging — the output schema is wider, not a separate call).

**Current schema:**
```json
{
  "relevant": true,
  "relevance_score": 7,
  "one_line_why": "...",
  "condition_tag": "A",
  "high_impact": true
}
```

**Extended schema:**
```json
{
  "relevant": true,
  "relevance_score": 7,
  "one_line_why": "...",
  "condition_tag": "A",
  "high_impact": true,
  "direction": "bullish",
  "magnitude": "high",
  "timeline_shift": "none"
}
```

**Field definitions:**

| Field | Type | Values | LLM instruction |
|---|---|---|---|
| `direction` | enum | `bullish` / `bearish` / `neutral` | "Does this event make YES resolution more likely (bullish), less likely (bearish), or neither (neutral)?" |
| `magnitude` | enum | `high` / `medium` / `low` | "How much does this event move the needle? High = materially changes probability. Medium = notable but not decisive. Low = incremental signal." |
| `timeline_shift` | enum | `sooner` / `later` / `none` | "Does this event suggest the contract will resolve sooner or later than the current expected timeline? Use 'none' if timing is unaffected." |

### Mechanism classification (no LLM)

Derived deterministically from `update_type`:

| Mechanism | update_type values |
|---|---|
| **Binding Action** | enforcement, final rule |
| **Signal** | proposed rule, advisory, guidance, comment request |
| **Context** | speech, press release, bulletin, trend report, standard, insights, event announcement, newsletter |

This is a pure lookup — implemented as a constant dict, not an LLM call.

### Net direction (portfolio aggregation)

For the portfolio list view's "Net direction" column, aggregate across recent events (last 30 days) for each contract:

```
bullish_count = count of events with direction == "bullish"
bearish_count = count of events with direction == "bearish"

if bullish_count > bearish_count * 1.5: "Bullish"
elif bearish_count > bullish_count * 1.5: "Bearish"
else: "Mixed"
```

Simple majority with a 1.5x threshold to avoid "Bullish" on a 3-2 split. No LLM needed.

---

## Probability Data Pipeline

### New build step: price fetcher

A new build module (`build/_prices.py`) that fetches and caches probability time series:

**Kalshi contracts:**
```
GET https://external-api.kalshi.com/trade-api/v2/series/{series}/markets/{ticker}/candlesticks
  ?period_interval=1440&start_ts={listed_ts}&end_ts={now_ts}
```
For resolved contracts, use the `/historical/` variant.

**Polymarket contracts:**
1. Fetch market metadata from Gamma API to get CLOB token ID
2. Fetch price history: `GET https://clob.polymarket.com/prices-history?market={token_id}&interval=max&fidelity=720`

**Cache:** `build/_cache/prices/{contract_id}.json` — committed to git (same pattern as LLM cache). Contains:
```json
{
  "contract_id": "kxbtc-maxprice-2026",
  "platform": "kalshi",
  "ticker": "KXBTC-MAXPRICE-2026",
  "fetched_at": "2026-05-25",
  "series": [
    {"t": 1703808000, "p": 0.45},
    {"t": 1703894400, "p": 0.51}
  ]
}
```

Normalized to `{t, p}` format regardless of source platform. `p` is probability (0.0-1.0).

**Graceful degradation:** If API is unreachable, use cached data. If no cache exists, the probability chart section renders with a "Price data unavailable" placeholder.

---

## Contract Portfolio

### Existing contracts (reused from gamma demo)

| # | ID | Platform | Title | Heat | Kind |
|---|---|---|---|---|---|
| 1 | kxbtc-maxprice-2026 | Kalshi | Will BTC hit $150K in 2026? | Critical | active |
| 2 | kxfeddecision-28jan | Kalshi | Fed rate decision (Jan 28) | Critical | active |
| 3 | us-recession-in-2026 | Polymarket | US recession in 2026? | Hot | active |

### New contracts

| # | ID | Platform | Title | Heat | Kind |
|---|---|---|---|---|---|
| 4 | sec-eth-security-2026 | Polymarket | Will SEC classify Ether as a security by 2026-12-31? | Hot | active |
| 5 | kxuschina-tariffs-2026 | Kalshi | Will US tariffs on Chinese goods exceed 60% in 2026? | Critical | active |
| 6 | fatf-travel-rule-2027 | Polymarket | Will 25+ FATF members adopt VASP Travel Rule by 2027-06-30? | Watch | active |

### Retrospective contracts (reused from gamma demo)

| # | ID | Platform | Title | Outcome |
|---|---|---|---|---|
| R1 | solana-etf-2025 | Polymarket | Will SEC approve spot Solana ETF in 2025? | YES |
| R2 | tiktokban-25apr30 | Kalshi | Will TikTok be banned by April 30, 2025? | YES |

### Synthetic positions (demo data, badged)

| Contract | Position | Entry price |
|---|---|---|
| kxbtc-maxprice-2026 | 200 YES | $0.54 |
| kxfeddecision-28jan | 100 NO | $0.71 |
| us-recession-in-2026 | 500 YES | $0.18 |
| sec-eth-security-2026 | 150 YES | $0.33 |
| kxuschina-tariffs-2026 | 300 YES | $0.47 |
| fatf-travel-rule-2027 | 100 YES | $0.61 |

---

## Navigation

```
[Carver] [Portfolio ▾] [Case Studies]        [Alex's Portfolio]

Portfolio dropdown:
  - List View (default)
  - Calendar View
```

- **Carver** — logo/home link, returns to portfolio list
- **Portfolio** — dropdown toggle between list and calendar views
- **Case Studies** — links to retrospectives landing
- **Alex's Portfolio** — persona indicator (right-aligned, decorative)

No full persona cards or character narratives (unlike the platform demos). The trader is the user, not a fictional character.

---

## Technical Architecture

### Build pipeline

Same static-site pattern as existing Pred-Oracle demo. New modules:

| Module | Purpose | LLM? |
|---|---|---|
| `build/_prices.py` | Fetch + cache probability time series from Kalshi/Polymarket APIs | No |
| `build/_relevance.py` (modified) | Extended output schema: adds direction, magnitude, timeline_shift to existing relevance call | Yes (existing call, wider schema) |
| `build/_mechanism.py` | Deterministic mechanism classification from update_type | No |
| `build/_portfolio.py` | Aggregate per-contract data into portfolio-level sort/filter data + net direction | No |
| `build/_calendar.py` | Extract future-dated events across all portfolio contracts, build calendar data structure | No |
| `build/trader_contract.py` | Slice generator for trader contracts (analogous to `gamma_contract.py`) | No |
| `build/trader_contract_enrich.py` | Enrichment orchestrator for trader contracts (analogous to `gamma_contract_enrich.py`) | Yes |
| `build/trader_site.py` | Jinja template renderer for all trader pages | No |

Note: `_relevance.py` is a modification of the existing module, not a new file. The direction/magnitude/timeline_shift fields are added to the same LLM call that already judges relevance — no additional API calls.

### Templates

All new Jinja2 templates in `build/templates/trader/`:
- `list.html` — portfolio list view
- `calendar.html` — portfolio calendar view
- `briefing.html` — contract briefing (shared by active + retrospective, with conditionals)
- `retrospectives.html` — case studies landing
- `_base.html` — shared layout, nav, styles

### Data files

New data files in `data/`:
- `data/trader-curation.yml` — portfolio contract picks, synthetic positions, demo configuration
- `data/platforms/{platform}/contracts/{id}.yml` — contract YAML for the 3 new contracts (same schema as existing)

### CSS/JS

The demo uses the same design system as the existing Pred-Oracle site (Tailwind via CDN, ECharts for charts). New JS needed for:
- Sort/filter on the list view (client-side, no framework)
- Calendar rendering (ECharts calendar heatmap — already in the stack)
- Probability chart with event markers (ECharts line chart + markLine)
- Month navigation on calendar view

---

## What's explicitly out of scope

- Real-time data / live updates (this is a static demo)
- User authentication or real portfolio management
- Trade execution or order placement
- Mobile-responsive layout (desktop-first, like the existing demos)
- Price alerts or notifications
- Historical backtesting tools
- Comparison between contracts
