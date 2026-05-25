# γ Scene Walkthrough — "Before You List, Look"

> **Stage 2 deliverable.** Second scene in the demo. Shifts protagonist from compliance to listing/trading-risk and shifts narrative from "react" to "anticipate".
>
> **Prerequisites:** Stage 1 (α) shipped. The site shell, navigation, and base templates already exist.

---

## 1. Narrative

**Protagonist:** "Marcus Vega," Head of Listing at the platform (fictional name; clearly labelled).

**Setting:** Tuesday morning, sometime after Sara Chen has triaged her inbox in Stage 1. Marcus is reviewing two things: a proposed new contract that the trading desk wants to list this week, and the regulatory heat on the platform's existing book of active contracts.

**Beats:**

1. **Pre-listing scan.** Marcus drops the proposed contract title and resolution criteria into Pred-Oracle's scan tool. Within 2 seconds, he sees the entities the contract resolves against (real regulators and corporations), a severity score, and the recent regulatory activity touching each entity.
2. **Contract-watch board.** Marcus pulls up the platform's active contracts, sorted by regulatory heat. One stands out — its heat score has spiked over the last 14 days.
3. **The retrospectives.** Marcus clicks into two real Kalshi contracts:
   - **TIKTOKBAN-25APR30** — settles on FCC + CFIUS + Department of Commerce + ByteDance + TikTok actions across early-to-mid 2025. The timeline shows the full real-world saga rendered as a Carver-annotated event sequence.
   - **KXFEDDECISION-26MAR** — settles on a single FOMC announcement, but pricing throughout the run-up moved on regional Fed speeches, Treasury actions, and CPI prints. The timeline shows the institutional-grade signal density.

   Both pages render the actual contract price overlay (from public Kalshi `prices-history`) against Carver signals, with annotations calling out cases where Pred-Oracle would have surfaced a signal before the news cycle.

**Time on scene:** ~4-5 minutes.

**Tone:** competent, analytical. Marcus is making a business decision; the product is decision-support, not entertainment.

---

## 2. Page-by-Page

### 2.1 γ Intro

- **Route:** `/gamma/`.
- **Template:** `build/templates/gamma/intro.html`.
- **Data slice:** none.

**Layout:**

1. **Scene framing strip:** "2 / 3 · Tuesday, 10:30 AM. You are **Marcus Vega**, Head of Listing. The trading desk wants a new contract live by Friday."
2. **Three-card grid summarizing what's coming:**
   - Card A — "Run a pre-listing scan." With a small icon and one-line: *"Paste the title and resolution criteria of a proposed contract. See its regulatory exposure before you list."*
   - Card B — "Watch the book." *"Every active contract scored for live regulatory pressure. Catch the heat early."*
   - Card C — "Learn from the past." *"Reconstruct any past contract's regulatory timeline. See what Pred-Oracle would have surfaced before the news did."*
3. **Primary CTA:** "Start with the scan tool →" pointing at `/gamma/scan/`.

### 2.2 Pre-Listing Scan

- **Route:** `/gamma/scan/`.
- **Template:** `build/templates/gamma/scan.html`.
- **Data slice:** `build/page_data/gamma/pre-listing-scans/{id}.json` (one per pre-rendered scan).

**Pre-rendered scans:**

| ID | Title | Why this scan |
|---|---|---|
| `tiktokban` | "Will TikTok be banned in the United States by 2026-12-31?" | Real Kalshi-style contract. Settlement entities (FCC, CFIUS, Commerce, ByteDance, TikTok) are all in `data/carver-events.json` via the regulator allowlist. Severity 8. |
| `solana_etf_2027` | "Will the SEC approve a spot Solana ETF in 2027?" | Real Polymarket-style contract. Settlement entities (SEC, BlackRock, named ETF applicants). Severity 7. |
| `state_kalshi_action` | "Will a 12th US state issue a cease-and-desist against Kalshi by 2026-12-31?" | Reflexively interesting (the platform is itself the asset). Settlement entities: 50 US state gambling regulators. Severity 9. |

**Layout (single-page form-then-results):**

1. **Header:** "Pre-listing scan — proposed contract".
2. **Input card** (always visible):
   - Title textarea (pre-filled with the active scan's title; visitor can switch via tabs at the top).
   - Resolution criteria textarea (pre-filled).
   - "Run scan" button.
   - Tabs above the form for the three pre-rendered scans: TikTok ban · Solana ETF · State action against Kalshi. Click a tab → load that scan into the form and the results below.
3. **Results panel** (below the form):
   - **Severity badge** large, color-coded.
   - **Severity breakdown** card: number of recent events, max urgency among matches, top driving entity.
   - **Extracted entities** chips: each entity with its source label ("from settlement_entities", "from regulatory_source allowlist", or "LLM-extracted").
   - **Recent regulatory activity** list (top 10 events touching the entities), grouped by entity, each event showing: title, source, pub date, urgency, primary-source link.
   - **Warnings** strip if any entity confidence was low.
4. **Bottom CTA:** "Open contract-watch board →" pointing at `/gamma/dashboard/`.

**Wow moment:** the TIKTOKBAN scan returns *real* recent regulatory activity touching the FCC / CFIUS / ByteDance / TikTok — not made-up. A prospect from Kalshi who actually listed this contract recognizes the events.

### 2.3 Contract-Watch Dashboard

- **Route:** `/gamma/dashboard/`.
- **Template:** `build/templates/gamma/dashboard.html`.
- **Data slice:** `build/page_data/gamma/contracts.json`.

**Layout:**

1. **Header:** "Active contracts by regulatory heat".
2. **Platform toggle:** "All / Kalshi / Polymarket" pill (visual filter; the slice contains both).
3. **Contracts table:**
   - Columns: Heat score (large number + 14-day sparkline) · Title (clickable) · Platform · Status · Entities (chips, top 3 + overflow count) · Last event · Open tickets badge (count of `kind='gamma_listing_risk'` tickets).
   - Default sort: heat DESC.
   - 10 contracts (5 Kalshi + 5 Polymarket from `data/platforms/*/contracts.yml`).
4. **Quick filter strip:** heat ≥5 / ≥7 / ≥9 (visual chips).
5. **Right rail:** "What's heating up?" — a short narrative summary auto-generated at build time naming the 1-2 fastest-rising contracts (heat-score delta over last 7 days).

**Wow moment:** the sparklines tell a story. At least one contract should show a clear rising edge over the prior two weeks (selected during data prep), which Marcus would otherwise have to compute by hand.

### 2.4 Contract Detail (5 Pre-Rendered)

- **Route:** `/gamma/contracts/{id}/`.
- **Template:** `build/templates/gamma/contract_detail.html`.
- **Data slice:** `build/page_data/gamma/contracts/{id}.json`.

Five contracts are pre-rendered as full detail pages. **Two are the wow retrospectives — TIKTOKBAN-25APR30 (dramatic, multi-agency saga) and KXFEDDECISION-26MAR (institutional, FOMC-driven).** The other three flesh out the dashboard with a state-action reflexive contract, a Polymarket Fed-rate equivalent for cross-platform comparison, and one additional active contract from each platform's current top-heat list.

**Layout:**

1. **Contract header:**
   - Title (clickable → primary source on Kalshi or Polymarket).
   - External ID, platform, status, listed-at, expires-at.
   - Large heat-score card with current value and 90-day trend chart.
2. **Settlement entities** section: chips with role tags (regulator / company / individual), editable in production (greyed out in demo with tooltip).
3. **Regulatory timeline:** the core of the page.
   - Horizontal time axis (last 90 days for active contracts; full history for the retrospectives).
   - Events marked as vertical bars; height = severity.
   - Click event → side panel with full Carver annotation.
   - **For the two retrospective contracts (TIKTOKBAN-25APR30, KXFEDDECISION-26MAR) and the Polymarket retrospective (Solana ETF 2025):** the live public APIs no longer serve retired contracts (verified at Stage 2 planning — Kalshi `prices-history` returns 404, Polymarket `slug` lookup returns empty). The retrospective wow shifts from price-overlay to **temporal-precedence math**: for each event marked on the timeline, render `signal_precedence_days = (first_carver_event_date − first_news_article_date)` as an annotation badge — "Pred-Oracle signal preceded news cycle by N days" — backed by both the Carver `pub_date` and a linked news article URL. Both dates are publicly verifiable per spec §6 source-of-truth discipline.
4. **Linked events list:** paginated table of events linked via `contract_event_links` logic from data-prep slicing.
5. **Open tickets** section: list of `kind='gamma_listing_risk'` synthetic tickets, with a "demo data" badge.

**Wow moments (the two retrospective pages):**
- **TIKTOKBAN**: a multi-agency timeline (FCC, CFIUS, Commerce, ByteDance) compressed into one page. Each event annotated with "Carver-annotated CFIUS filing surfaced N days before the AP wire." Real Carver `pub_date` vs real news-article URL; both linkable, both dated. No price overlay (the live Kalshi API no longer serves retired-contract price history).
- **KXFEDDECISION**: institutional-density view — Treasury, regional Fed, BLS, and FOMC signal cluster around the rate decision. Same temporal-precedence callouts. Density of signals (N≥10 in the 30 days before the decision) is the wow, not the price line.

---

## 3. Copy & Tone

- Marcus is direct. Page headers are imperative or matter-of-fact ("Run a pre-listing scan", "Active contracts by regulatory heat").
- The two retrospective pages (TIKTOKBAN, KXFEDDECISION) use retrospective framing copy ("If your team had been running Pred-Oracle in [period]…"). Other pages stay in present tense.
- "Pred-Oracle would have…" claims are made only on the retrospective and are factually grounded — the events listed are real, dated, and pre-news.

---

## 4. Interaction Details

| Interaction | Behavior |
|---|---|
| Click a scan tab | Re-render results panel for the chosen scan; URL fragment updates so the back button works. |
| Click "Run scan" | Pre-rendered scan results already visible; clicking shows a 1.2s fake spinner animation then nothing (results don't change). Tooltip: "Production deployment runs this synchronously against live Carver data." |
| Click a contract row | Navigate to `/gamma/contracts/{id}/`. |
| Click an event on the timeline | Slide-in side panel with full Carver annotation. Close button returns to timeline. |
| Hover sparkline | Show 14-day data points as tooltip. |
| Click "Open ticket" on a listing-risk ticket | Navigate to a stub α-style ticket detail (reused template) with the γ kind label. |

---

## 5. Acceptance Criteria (Stage 2)

- [ ] γ intro page renders and links work.
- [ ] All three pre-listing scans render full results with: severity badge, breakdown, extracted entities (≥2 each), recent events (≥3 each from real Carver pull).
- [ ] Contract-watch dashboard shows 10 contracts with sparklines; sort by heat works (it's the default).
- [ ] At least one contract shows a clearly-rising sparkline trend over its visible window.
- [ ] All 5 contract-detail pages render. The two retrospective Kalshi pages (`tiktokban-25apr30`, `kxfeddecision-26mar`) and the Polymarket retrospective (`solana-etf-2025`) each include ≥3 "Pred-Oracle signal preceded news by N days" callouts, with linked Carver `pub_date` and news-article date.
- [ ] TIKTOKBAN and KXFEDDECISION retrospective annotations match dates verifiable against public news.
- [ ] Linked events on each contract page are real (no fabricated events).
- [ ] Open-ticket synthetic content carries the demo-data badge.
- [ ] "Next scene" CTA on the last γ page in the narrative flow navigates to `/beta/`.
- [ ] Carver leadership dry-run: scene 2 plays end-to-end in ≤5 minutes; the TIKTOKBAN retrospective produces a recognizable reaction.
- [ ] Mobile: timeline reflows to a vertical list under 768px; sparklines remain readable.

---

## 6. Open Questions (γ-walkthrough-local)

| # | Question | Suggested resolution |
|---|---|---|
| GW1 | Will the TIKTOKBAN and KXFEDDECISION events be sufficiently covered by the Carver pull? | TIKTOKBAN saga ran 2024-2025; FOMC/Fed-rate coverage is ongoing. Both should land cleanly with the 2024-01-01+ date range. Verify at Stage 0 by sampling the carver-feeds-sdk for FCC + CFIUS + ByteDance entities (TIKTOKBAN) and FOMC + Federal Reserve (KXFEDDECISION). Broaden if coverage gaps appear. |
| GW2 | Where does the contract price data on the retrospective pages come from? | Kalshi exposes a public `prices-history` endpoint at `external-api.kalshi.com/trade-api/v2/markets/{ticker}/prices-history`. Pull at build time for each retrospective contract; store snapshot as `data/platforms/kalshi/contracts/{external_id}_history.csv` with a `source_url` + `pulled_at` header comment. |
| GW3 | Should the demo's pre-listing scan permit a free-text submission where the visitor types their own contract? | Tempting but dangerous — the results panel is pre-rendered; an unrecognized submission would either show stale results or require live computation. Out of scope for the static demo. Tab-based selection of pre-rendered scans is the right move. |
| GW4 | TIKTOKBAN-25APR30 resolved in real life — does showing it as a "pre-listing scan" feel anachronistic? | Frame as a *retrospective pre-listing scan*: "If your team had run this scan in January 2025, here's what Pred-Oracle would have shown." Add the framing copy at the top of that scan tab. |
| GW5 | Polymarket Trump-administration contract — politically sensitive? | Pick a politically-neutral resolution event (e.g., a Cabinet confirmation timing market, not a policy-position market). Or substitute with a different real Polymarket contract. Defer choice to Stage 2 kickoff. |
| GW6 | "Pred-Oracle would have surfaced this N days earlier" — what's the source of the N? | The earliest Carver-annotated event matching the contract's settlement entities, compared to the date of the first mainstream news article. Both dated, both linked. N must be honest. |
| GW7 | Why no price overlay on retrospectives? | The Kalshi `prices-history` endpoint returns 404 for retired contracts (verified 2026-05-20). The Polymarket CLOB returns empty `history` arrays for unknown markets. Rather than fabricate price data, the wow shifts to Carver-vs-news temporal-precedence math, which preserves source-of-truth discipline. |
