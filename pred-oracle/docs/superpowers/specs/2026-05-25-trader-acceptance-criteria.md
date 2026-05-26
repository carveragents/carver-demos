# Trader Dashboard — Acceptance Criteria

Criteria for verifying the trader dashboard demo is user-ready. Each criterion describes what the user sees or does, and the expected result. Test against a full build with real corpus data and cached prices.

**Direction convention throughout:** "bullish" always means the event increases the probability of the contract resolving YES. "bearish" means it decreases that probability. This is a property of the event relative to the contract, not relative to any individual position.

---

## AC-1: Portfolio List View

### AC-1.1: Page loads with all contracts
- Navigate to `/trader/`
- **Expected:** Page title "Your Portfolio", 3 contract rows visible, subtitle shows "3 contracts"

### AC-1.2: Each contract row shows required signals
- For each of the 3 rows, verify all of these are present:
  - Heat tier badge (one of: CRITICAL red, ACTIVE orange, WATCH amber, DORMANT gray)
  - Platform chip (Kalshi or Polymarket)
  - Contract title
  - Price display: "YES {price}c" and "NO {price}c" with non-placeholder, non-blank values
  - Net direction indicator: one of "Bullish" (green arrow up), "Bearish" (red arrow down), or "Mixed" (gray arrow right)
  - Heat score number + 7d delta (with + or - sign)
  - Event count ("N key events") — label is "key events", not "events / 90d"
  - Latest event line: date + event title + direction badge
  - Position with DEMO badge (e.g., "YES 200 @ 54c")

### AC-1.3: Contracts sorted by heat
- **Expected:** Rows ordered by heat score descending. The contract with the highest heat value appears first.

### AC-1.4: Sort controls work
- Click "Direction" sort button
- **Expected:** Rows reorder (Bullish first, then Mixed, then Bearish)
- Click "Heat" sort button
- **Expected:** Rows return to heat-descending order

### AC-1.5: Platform filter works
- Click "Kalshi" filter
- **Expected:** Only Kalshi contracts visible (2 rows). Polymarket rows hidden.
- Click "All" filter
- **Expected:** All 3 rows visible again

### AC-1.6: Tier filter works
- Click any active tier filter (e.g., "Critical")
- **Expected:** Only contracts with that tier visible. Other rows hidden.
- Click "All" filter
- **Expected:** All 3 rows visible again

### AC-1.7: Contract row links to briefing
- Click any contract row
- **Expected:** Navigates to `/trader/contracts/{id}/` for that contract

### AC-1.8: Calendar toggle
- Click "Calendar view" link
- **Expected:** Navigates to `/trader/calendar/`

### AC-1.9: At least one contract shows a "Next catalyst"
- **Expected:** At least one of the 3 rows shows a future date with event title (e.g., "Next catalyst: CFTC custody rule effective · Jun 8")

### AC-1.10: No personal names on the page
- **Expected:** No first-name + last-name combinations appear as rendered text. Persona names ("Priya Kapur", "Marcus Vega", etc.) are configuration data only and must not appear in the UI.

---

## AC-2: Calendar View

### AC-2.1: Page loads with month grid
- Navigate to `/trader/calendar/`
- **Expected:** Page title "Regulatory Calendar", event count subtitle, monthly calendar grid with Sun-Sat headers

### AC-2.2: Month heading visible
- **Expected:** Current month name and year displayed between prev/next navigation arrows (e.g., "May 2026")

### AC-2.3: Day numbers visible
- **Expected:** Each cell in the calendar grid shows its day number (1-31)

### AC-2.4: Color-coded event dots on dates
- **Expected:** Dates with regulatory events show colored dots:
  - Green = bullish event
  - Red = bearish or high-impact event
  - Amber = medium-impact event
  - Blue = settlement/expiration date
  - Purple = effective date
  - Dots are present on at least 5 distinct dates

### AC-2.5: Month navigation works
- Click the forward arrow
- **Expected:** Calendar advances to next month. Heading updates.
- Click the back arrow
- **Expected:** Calendar returns to current month.

### AC-2.6: Date click expands event details
- Click on a date that has event dots
- **Expected:** An expanded panel appears below the calendar showing event details for that date (title, contract, direction)

### AC-2.7: Recent events ticker
- **Expected:** A horizontal strip below the header shows recent events with direction arrows and event titles

### AC-2.8: List view toggle
- Click "List view" link
- **Expected:** Navigates back to `/trader/`

### AC-2.9: Coverage footnote visible
- **Expected:** Bottom of page shows footnote about data coverage limitations

---

## AC-3: Contract Briefing

### AC-3.1: Page loads with contract header
- Navigate to `/trader/contracts/{any-id}/`
- **Expected:** Contract title as h1, platform chip, heat tier badge, expiry date

### AC-3.2: Price buttons display real prices
- **Expected:** YES and NO price buttons show non-placeholder, non-blank prices (not 50c/50c for active contracts). Payout math shows a real number (e.g., "payout $161/$100")

### AC-3.3: Position display
- **Expected:** "Your position: {YES|NO} {N} contracts @ {price}c avg" with DEMO badge

### AC-3.4: Probability chart renders
- **Expected:** An ECharts line chart is visible showing the probability over time (x-axis: dates, y-axis: 0-100%). The chart has at least 10 data points forming a visible line.

### AC-3.5: Regulatory event markers on chart
- **Expected:** Vertical colored markers (green/red/gray) overlaid on the probability chart at event dates. Hovering a marker shows a tooltip with event title and one-line-why.

### AC-3.6: Thesis tracker
- **Expected:** Section titled "Thesis tracker" with 1-3 conditions (A/B/C), each showing:
  - Condition label and summary
  - Progress bar with green (bullish) and red (bearish) segments
  - Event count per direction

### AC-3.7: Regulatory timeline
- **Expected:** Section titled "Regulatory timeline (N)" with a vertical list of events, each showing:
  - Date + regulator name
  - Event title (clickable, links to real source URL — not example.com)
  - Direction badge: "bullish" (green), "bearish" (red), or "neutral" (gray)
  - Magnitude icon: filled circle (high), half circle (medium), outline circle (low)
  - Mechanism label: "Binding Action", "Signal", or "Context"
  - Condition dot (colored to match thesis tracker)
  - One-line-why explanation text

### AC-3.8: Direction badge consistent with explanation
- For each event in the timeline, the direction badge must not contradict the one-line-why:
  - If one_line_why says "increases odds", "raises probability", or "boost": direction must be **bullish**
  - If one_line_why says "decreases odds", "lowers probability", or "hinders": direction must be **bearish**
  - **Expected:** Zero self-contradictions visible across all timeline events

### AC-3.9: Low-relevance events show neutral
- **Expected:** Events described as tangential, indirect, or background context always carry "neutral" direction — no bullish or bearish badge on events whose one_line_why indicates only weak or ambiguous relevance

### AC-3.10: Timeline shift indicators
- For events where timeline shift is not "none":
  - **Expected:** A clock icon with "Sooner" or "Later" label appears on the event
- For events where timeline shift is "none":
  - **Expected:** No clock icon or shift label shown

### AC-3.11: Narrative summary
- **Expected:** A blockquote section titled "Analyst narrative" with 2-3 sentences of LLM-generated narrative

### AC-3.12: Momentum panel (sidebar)
- **Expected:** Right sidebar shows:
  - Heat score number + tier badge
  - 7d delta with directional sign
  - Peer percentile (e.g., "top 5% of peers")
  - 14-day sparkline visualization
  - Primary drivers (1-3 bullet points)
  - One-sentence explainer text

### AC-3.13: Upcoming catalysts (sidebar)
- If the contract has events with future effective_date or comment_deadline:
  - **Expected:** "Upcoming catalysts" section shows the dates with countdown and event title
- If no future dates exist:
  - **Expected:** Section shows "No upcoming regulatory dates on record"

### AC-3.14: Back navigation
- Click "← Portfolio"
- **Expected:** Navigates back to `/trader/`

### AC-3.15: Resolution banner (retrospective only)
- Navigate to `/trader/retrospectives/{id}/`
- **Expected:** A banner at top shows the resolution outcome (e.g., "Resolved YES on {date}")

---

## AC-4: Retrospective Case Studies

### AC-4.1: Landing page lists case studies
- Navigate to `/trader/retrospectives/`
- **Expected:** Page title "Case Studies", intro paragraph, 2 cards (Solana ETF + TikTok Ban)

### AC-4.2: Each card shows required info
- **Expected:** Each card displays:
  - Contract title
  - Platform chip
  - Resolution badge ("Resolved YES" or similar)
  - Narrative snippet
  - Clickable link to detail page

### AC-4.3: Detail page renders as briefing
- Click a case study card
- **Expected:** Navigates to `/trader/retrospectives/{id}/`, renders the same briefing layout as AC-3 with:
  - Resolution banner at top
  - Full probability chart from listing to resolution
  - Complete regulatory timeline with directional enrichment
  - Narrative in past tense

---

## AC-5: Navigation Flow

### AC-5.1: Portfolio nav links
- From any page, "Portfolio" link in top nav navigates to `/trader/`
- "Case Studies" link navigates to `/trader/retrospectives/`

### AC-5.2: Breadcrumb consistency
- Contract briefing pages show "← Portfolio" back link
- Retrospective detail pages show "← Portfolio" or "← Case Studies" back link

### AC-5.3: Cross-page contract continuity
- A contract card on the list view shows heat = X
- Click into that contract's briefing page
- **Expected:** The momentum panel shows the same heat value X

---

## AC-6: Data Integrity

### AC-6.1: Three distinct contracts in portfolio
- **Expected:** The 3 active contracts cover distinct themes: crypto price (BTC max price), monetary policy (Fed decision), and macro risk (US recession)

### AC-6.2: Platform spread
- **Expected:** Active portfolio: 2 Kalshi contracts, 1 Polymarket contract. Retrospectives: 1 of each platform.

### AC-6.3: Heat tiers reflect regulatory activity
- **Expected:** Each contract's heat tier is consistent with the volume and recency of its regulatory events. A contract with 15+ recent high-urgency events should not show "dormant". Heat tiers are data-driven, not manually set.

### AC-6.4: Demo data clearly labelled
- **Expected:** Every synthetic element (positions) has a visible DEMO badge. No synthetic data presented without a badge.

### AC-6.5: Real regulatory event source URLs
- Click any event title link in the timeline
- **Expected:** Links to a real regulatory source URL (CFTC, SEC, Federal Reserve, etc.) — not example.com and not a broken link

### AC-6.6: Non-neutral event rate across portfolio
- **Expected:** Across the combined timelines of all contracts, at least 15% of events carry a bullish or bearish direction. All-neutral across the full portfolio indicates the enrichment pipeline is not functioning. (Current baseline: ~22%)

### AC-6.7: No personal names on any rendered page
- Navigate all pages (portfolio list, calendar, briefings, retrospectives)
- **Expected:** No first-name + last-name combinations appear. Persona names are internal configuration only.

### AC-6.8: Prices are real and current
- **Expected:** YES/NO prices on the portfolio list and briefing pages come from the Kalshi or Polymarket API (fetched within the last 7 days). No contract should show 50c/50c on the portfolio list unless it genuinely trades at that price.

---

## AC-7: Edge Cases

### AC-7.1: Contract with no upcoming catalysts
- **Expected:** "No upcoming regulatory dates on record" shown in sidebar, not a blank section or error

### AC-7.2: Contract with sparse event data
- If any contract timeline has fewer than 5 events:
  - **Expected:** The timeline renders without errors. The thesis tracker still renders (may show zero counts). No broken layout.

### AC-7.3: Empty calendar month
- Navigate to a month with no events (use prev/next arrows)
- **Expected:** Calendar renders an empty grid with day numbers. No errors or broken layout.

### AC-7.4: Signal variety across portfolio
- Across all 5 contracts (3 active + 2 retrospectives), verify at least one instance each of:
  - Direction: bullish, bearish, neutral
  - Magnitude: medium, low (high-magnitude events are rare and may not always be present)
  - Mechanism: Binding Action, Signal, Context
  - Timeline shift: sooner, later (at least one of each, somewhere across all timelines)
