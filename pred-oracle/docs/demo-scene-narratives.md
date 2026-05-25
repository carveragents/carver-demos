# Demo Scene Narratives — Reference for Demo Video Iterations

**Purpose:** Capture the "why this exists / what it proves / how the pieces connect" narrative behind each demo scene. Future iterations of the demo video (or any demo asset) should read this **before** drafting storyboard narration so the narrator articulates the underlying logic, not just what's visible on screen.

**Companion docs:**
- The creative brief for the demo video: [`docs/superpowers/specs/2026-05-21-demo-video-brief.md`](superpowers/specs/2026-05-21-demo-video-brief.md)
- The product strategy doc that authored the underlying use cases: [`docs/product-strategy.md`](product-strategy.md)
- The β curation file that drives the live data picks: [`data/beta-curation.yml`](../data/beta-curation.yml)

---

## Scene α — The GC's Monday morning (Radar)

**Persona:** Sara Chen, General Counsel.

**Audience hat that lights up:** GC, CCO.

**The question it answers:** "Did a regulator just do something that affects *us* — and have I assigned it to someone?"

**What's wrong with the status quo:** Today, GC teams answer this with Google Alerts, Twitter, journalist tips, and law-firm panels — slow, lossy, unstructured. Kalshi reportedly spent days reacting to each new state cease-and-desist order. There's no triage queue, no audit log, no defensible paper trail.

**What this scene proves:**
1. The signal exists in structured form (Carver's annotated corpus — 49,735 events, 99 jurisdictions, 157 regulatory bodies).
2. The platform turns each signal into an actionable workflow ticket — assignee, priority, urgency score, written rationale, discussion thread.
3. Every state transition is preserved in an audit log — the same paper trail a regulator or internal auditor would want.

**Anchor data:**
- α inbox shows the live triage queue with real CFTC/SEC/NY DFS/Florida OFR tickets.
- α ticket detail pages render a real SEC enforcement (David H. Goldman — broker-dealer suspension) with full workflow panel.
- α audit-export shows the transition log: "ingested → acknowledged → assigned → in review" — every state move stamped and exportable.

**What the demo narration must land:** *"This is operational, not analytical. The team would assign these tickets Monday morning and the GC has a defensible record by Friday."*

---

## Scene γ — Before you list, look (Listing risk)

**Persona:** Marcus Vega, Head of Listing.

**Audience hat that lights up:** Head of Markets, Listing-Risk, Compliance.

**The question it answers:** "Should we list this contract? And how is our active book aging against regulatory pressure?"

**What's wrong with the status quo:** Listing decisions on prediction markets are made by traders thinking about volume and edge, not by counsel reading the regulatory record. The first time anyone audits a contract's regulatory exposure is often after a state AG or the SEC has already moved.

**What this scene proves (three artifacts):**

1. **Pre-listing scan** — Drop a proposed contract title + resolution criteria. Get a severity score (0-10) computed against the entire annotated corpus, with the specific events and entities driving it. Demoed via three scenarios; the 12th-US-state cease-and-desist scenario is the strongest because Kalshi has already faced C&D in 7+ states.

2. **Active contract heatmap** — Every contract you've listed scored for live regulatory pressure over a 90-day window, sorted heat-descending. Each row: heat number, 14-day sparkline, 7-day delta, settlement-entity chips, last-event date, open tickets.

3. **Retrospective deep-dives** — Pick a resolved contract and walk the regulatory trail Pred-Oracle would have assembled. The Solana ETF retrospective is the centerpiece: 20 events from 2024-08 to 2025-12, each LLM-judged for relevance to the contract conditions, each with a one-line "why this matters" rationale.

**Anchor data:**
- 6 curated contracts on the dashboard (3 active, 3 resolved retrospectives).
- Solana ETF (20 events) > Federal Reserve March (12 events) > BTC max-price (20 events).
- Per-event LLM "why this matters" lines committed to git for reproducibility.
- Heat panel: tier label (dormant/watch/active/critical), value, 7-day delta, peer percentile, urgency-weighted sparkline, primary drivers, LLM explainer.

**What the demo narration must land:** *"This is what a listing-risk review looks like with Pred-Oracle in the room — a decomposed contract, a written storyline, a dated trail, and a defensible score."*

**Data caveat to keep in mind:** The Solana ETF page's LLM-generated narrative concludes the contract resolved NO (no clear SEC approval order in the timeline), while the source YAML says `resolution_outcome: YES`. The on-screen narrative is what's verifiable; narration must anchor to it. If a future iteration wants a clean YES-outcome retrospective, switch to `kxfeddecision-26mar` (12 events, narrative aligned with outcome).

---

## Scene β — Q3 planning, without the surprise (Expansion)

**Persona:** Priya Kapur, Head of International.

**Audience hat that lights up:** Head of International, CFO/Strategy, board-level decision-makers.

**The question it answers:** "Which of my open jurisdictions will close next quarter — and which closed ones might reopen?"

**What's wrong with the status quo:** Both Kalshi (140+ countries since Oct 2025) and Polymarket (USDC-native global distribution) operate in jurisdictions they have no structured visibility into. France's ANJ took 13 months from open-investigation to ban; Polymarket had 13 months of escalating signals to act on but no system to surface them. Same pattern repeated in Singapore, Thailand, UK, Netherlands within the same 18-month window. Each was a 12-month pattern hiding in plain sight.

**The headline narrative — the France case:**

> **France's gambling regulator ANJ banned a major prediction-market platform in December 2025, 13 months after opening its investigation.** Across those 13 months, the visible regulatory signals came from **AMF (French financial markets regulator), ESMA (EU-level securities regulator), and the EU Commission** — financial-market regulators escalating in parallel with the gambling regulator's investigation. Singapore, the Netherlands, the UK, and Taiwan followed within the same window.

This is the canonical proof case: **a real, recent, public regulatory exit where the warning signals were structured and visible for over a year — if you were looking.**

**Critical data caveat:** ANJ (the actual gambling regulator that issued the ban) is **not** in the Carver catalog. The 13-month sparkline on the heatmap is plotted from AMF + ESMA + EU Commission events tagged France — financial-regulator proxies for the escalating climate. The heatmap page acknowledges this in an "Honest framing" callout: *"Direct ANJ events are not in the Carver catalog. The timeline above is drawn from AMF, ESMA, and EU Commission events tagged France."* Future iterations must NOT claim ANJ events on screen unless ANJ data is actually ingested.

**The three artifacts on β intro and how they relate to France:**

The three boxes on `/beta/` are NOT three different stories about France. They are **three different ways of using the France pattern as a template** for live decision-making:

| Box | Question it answers | France connection |
|---|---|---|
| **A — Walk the world** (`/beta/heatmap/`) | "Where is heat building *right now*?" | World heatmap is the present-tense scan. Below the map sits the France 13-month retrospective sparkline — the **calibration case** that teaches the viewer what an escalation pattern looks like, so they can recognize it on the live world map above. |
| **B — Follow the cascades** (`/beta/cascades/`) | "When a global regulator (FATF / ESMA / BCBS) acts, which member states are likely to act next?" | France's pre-exit was a cascade: FATF/ESMA at the top, member-state action below. This page surfaces three cascades currently mid-flight — FATF virtual assets, BCBS disclosure frameworks, ESMA Q1 2026 event-contracts — and lists which member states historically follow. Same mechanic France played out in. |
| **C — Read the quarter** (`/beta/report/`) | "What's the board-ready summary?" | The auto-drafted Q2 2026 PDF names three watchlist jurisdictions whose patterns currently resemble France 12 months pre-exit: **Brazil, Singapore, Australia**. Each picked by `beta-curation.yml`'s `watch_list_picks` with explicit "pattern resembles French regulatory escalation 12 months out" rationale and 3 specific recommended actions. |

**Anchor data (from `data/beta-curation.yml`):**
- France retrospective focus: country FR, 18-month narrative window, 5 annotation callouts dated 2024-11 to 2025-12.
- Featured cascades: `fatf-2025-q4-virtual-assets`, `bcbs-2025-disclosure-frameworks`, `esma-2026-q1-event-contracts`.
- Watch list picks: Brazil (SECAP), Singapore (MAS), Australia (AUSTRAC + ACMA) — each with rationale and 3 recommended actions.
- Report window: 2026-04-01 to 2026-06-30 (Q2 2026).
- Platform footprint hint: `polymarket` (the outlined country footprint on the world map).

**Heatmap page layout (2026-05-21 onward — France-first):**

The `/beta/heatmap/` page is structured as a two-step calibrate-then-apply walk, not a present-tense world map followed by a retrospective:

1. **Header** — "Reading regulatory pressure" + lead-in copy.
2. **Step 1 · Calibrate** — France retrospective at the top: sparkline + 4 annotation callouts + the events list that fed the sparkline + the "Honest framing" amber callout about AMF/ESMA-as-ANJ-proxies.
3. **Step 2 · Apply** — World heatmap + US-states drilldown.

This ordering matches the new intro framing ("France is the case study. Each card applies that lens to a different question."). Section anchors are `#step-1-calibrate` and `#step-2-apply`.

**Demo storyboard implications (β beats 27-29):** the previously-recorded demo video (`pred-oracle-demo.mp4` dated 2026-05-21) walked the heatmap top-to-bottom under the OLD layout — world map at top, US inset middle, France at bottom. Future iterations must reverse this. Suggested new beats and approximate scroll positions (measured 2026-05-21):

| Beat | Action | scroll_y | What's on screen |
|---|---|---|---|
| 27 (open heatmap) | `goto /beta/heatmap/` | 0 | Header + France sparkline calibration block |
| 28 (France retro detail) | `scroll_y: 400` | 400 | Sparkline + 4 numbered callouts + start of events list |
| 29 (apply to today) | `scroll_y: 1180` | 1180 | "Step 2 · Apply" header + world heatmap |
| 29b (US drilldown, optional) | `scroll_y: 1750` | 1750 | US-states map |

Narration should reorder accordingly: France calibration first, then "apply that pattern to today's world", then optional US drill.

**What the demo narration must land:** *"This is the strategic layer. France was 13 months of pattern hiding in the record. Pred-Oracle gives a senior team that pattern in real time — for Brazil, Singapore, Australia, and every jurisdiction your platform currently operates in."*

---

## Cross-scene principles

These hold across all three scenes and should govern any future narration:

1. **Every visible claim must be verifiable on the page.** No invented numbers. If the narration says "100 matching events", that number must be on screen at that beat's frame.

2. **Initialisms must be hyphenated** for TTS: C-F-T-C, S-E-C, F-O-M-C, E-T-F, U-S, P-D-F, D-F-S, A-G, K-Y-B.

3. **Anchor to the persona, not the platform.** Each scene leads with "Monday/Tuesday/Wednesday morning. You are [name], [title]." This pulls the viewer into a workday, not a sales pitch.

4. **Land one wow moment per scene, not three.**
   - α wow: a real SEC enforcement is already a workflow ticket.
   - γ wow: the 20-event Solana ETF timeline with per-event "why this matters" lines.
   - β wow: the France 13-month sparkline embedded below the world map.

5. **The brief beats the storyboard.** When a future iteration runs, the writer should read `docs/superpowers/specs/2026-05-21-demo-video-brief.md` FIRST to understand audience + goals, then this doc to understand the underlying logic, then draft beats anchored to what's actually on the live pages.
