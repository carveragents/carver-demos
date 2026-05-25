# β Scene Walkthrough — "Q3 Planning, Without the Surprise"

> **Stage 3 deliverable.** Third and final scene. Shifts from per-event compliance and per-contract risk to longitudinal jurisdictional strategy. Closes the demo's narrative arc.
>
> **Prerequisites:** Stages 1 and 2 shipped.

---

## 1. Narrative

**Protagonist:** "Priya Kapur," Head of International / Corp Dev at a Polymarket-class platform (fictional name).

**Setting:** Wednesday morning. Q2 has just closed. The board meets in three days to review international strategy. Priya opens Pred-Oracle's expansion view.

**Beats:**

1. **The heat-map.** Priya looks at the world. France is dark — closed since Dec 2025. Several jurisdictions glow in increasing intensity over the last 90 days.
2. **The France retrospective.** Priya clicks on France. The drilldown reconstructs *13 months* of ANJ signals escalating before the actual Dec 2025 ban. The pattern is visible in retrospect.
3. **Cascade signals.** A real recent FATF guidance event dropped. Pred-Oracle's cascade-rule engine names ~39 member jurisdictions expected to act within the follow window. The ones currently in Priya's operating footprint are highlighted — the strategic blast radius is named explicitly.
4. **The auto-drafted report.** Priya opens the Q2 2026 quarterly report. Top sections: jurisdictions where pressure is rising, jurisdictions where it's falling, a watch list of "3 jurisdictions that look like France did 12 months ago." Backed by Carver document links. Downloadable PDF.

**Time on scene:** ~4-5 minutes.

**Tone:** strategic, sober. This is the scene that makes a Board agenda. The product narrates restraint — no over-claim.

---

## 2. Page-by-Page

### 2.1 β Intro

- **Route:** `/beta/`.
- **Template:** `build/templates/beta/intro.html`.
- **Data slice:** none.

**Layout:**

1. **Scene framing strip:** "3 / 3 · Wednesday, 11:00 AM. You are **Priya Kapur**, Head of International. Q3 planning is at the board on Friday."
2. **Lede paragraph:**
   > France's ANJ banned Polymarket in December 2025, 13 months after opening an investigation. Singapore, Thailand, UK, and Netherlands followed within the same window. Each surprise was a 12-month signal.
3. **Three-card grid:**
   - Card A — "Walk the world." Heat-map of jurisdictional pressure.
   - Card B — "Follow the cascades." When a standards body acts, which member states are next?
   - Card C — "Read the quarter." Auto-drafted Q2 intelligence report.
4. **Primary CTA:** "Open heat-map →" pointing at `/beta/heatmap/`.

### 2.2 World Heat-Map

- **Route:** `/beta/heatmap/`.
- **Template:** `build/templates/beta/heatmap.html`.
- **Data slice:** `build/page_data/beta/heatmap.json`.

**Layout:**

1. **Header:** "Jurisdictional regulatory pressure — last 90 days".
2. **Top controls strip:**
   - Date window dropdown: 30d / 90d (default) / 365d / "since pull". Visual only on most options; the slice contains pre-computed 90d and 365d aggregates.
   - Update-type filter chips.
   - Platform footprint toggle: Polymarket / Kalshi (changes the highlighted set on the map).
3. **World choropleth** (ECharts geo).
   - Country fill = event count in window × avg urgency (a composite score baked into the slice).
   - Color scale: green (low) → yellow → orange → red (high). Grey for "no data".
   - Tenant footprint: jurisdictions where the active platform is `operating` are outlined in blue; `considering` outlined in dashed blue; `closed` outlined in red (France, Singapore, etc. for Polymarket).
   - Tooltip: country, count, avg_urgency, max_urgency, current footprint status.
   - Click country → slide-in drilldown panel.
4. **US-states inset** (below): same logic for US-XX codes.
5. **Drilldown side-panel** (when a country is clicked):
   - Header: country name + footprint status + summary stats.
   - **Pressure-over-time chart:** 18-month line of weekly event counts. The chart for France should make the 13-month escalating slope obvious.
   - Event list: top 10 events in window, sorted by urgency × recency.
   - "Cascade signals affecting this jurisdiction" mini-section (cross-link to § 2.3).

**Wow moment:** France. The viewer clicks France, sees the 13-month slope build before the Dec 2025 cliff. Annotated callouts trace the escalation: *"AMF opens dossier on prediction-market activity Nov 2024 · ESMA Q1 2025 risk dashboard cites unregulated event-contract venues · AMF guidance on financial product perimeter July 2025 · enforcement notices Oct 2025 · public restriction announced Dec 2025."* All Carver-annotated, all linkable. (Direct ANJ events are not in the Carver catalog; AMF + ESMA + EU Commission coverage carries the timeline. Footer notes the gap.)

### 2.3 Cascade Signals

- **Route:** `/beta/cascades/`.
- **Template:** `build/templates/beta/cascades.html`.
- **Data slice:** `build/page_data/beta/cascade-signals.json`.

**Layout:**

1. **Header:** "Active regulatory cascades".
2. **Description block:** "When an international body publishes guidance, its member states historically follow. Pred-Oracle tracks these patterns and names the jurisdictions next."
3. **Cascade cards** (3-5 hand-curated):
   - Each card:
     - **Trigger event header:** body name (FATF / IOSCO / BCBS / EU Commission), guidance title, pub date, primary-source link.
     - **Rationale snippet:** one-paragraph analyst note.
     - **Expected followers chip-grid:** all member jurisdictions; tenant-footprint ones highlighted (operating → blue ring, considering → dashed, closed → struck-through).
     - **Time-to-window:** "Expected member-state actions through 2027-05-01" (based on follow_window_days).
     - **Click expand:** show prior cascades from same rule with hit-rate annotation (e.g., "Prior FATF guidance in 2022 was adopted by 31/39 members within 18 months").
4. **Right rail:** "How cascade rules work" — short explainer + link to the cascade-rule schema in `future/40-beta-strategic-expansion.md` for the technically curious.

**Wow moment:** the FATF cascade. The card shows a real recent FATF guidance event (from Carver), names the 39 member jurisdictions, highlights the half-dozen in Polymarket's operating footprint. Forces the board conversation: "Which of these do we exit, geofence, or invest in lobbying?"

### 2.4 Quarterly Intelligence Report

- **Route:** `/beta/report/`.
- **Template:** `build/templates/beta/quarterly_report.html`.
- **Data slice:** `build/page_data/beta/quarterly-report.json`.

The page is the auto-drafted Q2 2026 report rendered in browser. A "Download PDF" button delivers a pre-rendered static PDF artifact in `site/static/samples/q2-2026-report.pdf` (created during Stage 3 build or hand-rendered once).

**Layout (mirrors the PDF):**

1. **Cover strip:** "Q2 2026 Regulatory Expansion Intelligence — Polymarket (illustrative)" · generated date · "Source: Pred-Oracle (built on Carver regulatory annotations)".
2. **Headline-stats card row** (4 tiles):
   - Events in window.
   - Jurisdictions with activity.
   - High-urgency events (urgency ≥ 8).
   - Active cascade signals.
3. **Pressure rising** section: top 10 jurisdictions sorted by composite delta-rank.
   - Per jurisdiction: name + footprint status + delta vs prior quarter + 2-sentence narrative + 3 top driving events with primary-source links.
4. **Pressure easing** section: top 5 jurisdictions with declining pressure.
5. **Watch list** — *the key section*. 3 jurisdictions whose pattern resembles France's 12 months before the ban. Each names:
   - Why it's on the list (pattern match against `france_pre_ban_signature`).
   - Time-to-expected-action estimate.
   - Recommended actions ("Pred-Oracle staff recommendation: prepare geofencing posture · engage local counsel · monitor monthly").
6. **Cross-module sidebar (small):** "γ touchpoints" — top 3 active listed contracts whose heat scores correlate with jurisdictions on the watch list.
7. **Appendix:** all active cascade signals · method notes · data window · coverage caveats.
8. **Download PDF button.**

**Wow moment:** the watch list. The viewer doesn't expect Pred-Oracle to *name jurisdictions* — but it does, with evidence. This is the section that gets photographed on phones during the demo and brought into the next board meeting.

---

## 3. Copy & Tone

- Strategic, board-ready. No exclamation marks anywhere.
- Every claim about a jurisdiction has a footnote / primary-source link.
- The watch list explicitly hedges: "Pattern-based projection, not prediction. Confidence: medium."
- The report's footer is honest about the V1 cascade engine being rule-based: *"V1 cascade rules are curated from historical patterns. Learned models will replace rules in V2+ as more data accrues."*

---

## 4. Interaction Details

| Interaction | Behavior |
|---|---|
| Click country on world map | Slide-in drilldown panel; ESC or X to close. |
| Hover country | Tooltip with summary. |
| Toggle platform footprint Polymarket/Kalshi | Re-render highlighted outlines (no slice swap; the slice contains both footprints). |
| Click cascade card "expand" | Reveal historical hit-rate detail. |
| Click event link on heat-map drilldown | Open primary-source URL in new tab. |
| Click "Download PDF" on quarterly report | Open `site/static/samples/q2-2026-report.pdf` in new tab. |
| Click "Next" anywhere in scene 3 | Navigate to `/close.html`. |

---

## 5. Close Page (`/close.html`)

Lives outside β technically, but ships with Stage 3. Layout:

1. Recap strip: "α — radar / γ — listing / β — expansion. One spine. Real data."
2. Short paragraph: "Every signal in this demo came from Carver's regulatory-annotation pipeline. Your production deployment would pull live across the regulators relevant to your business."
3. Three small reminders of what was shown (one screenshot per scene).
4. CTA card: contact details / calendar link / "request a live data feed."
5. Footer: doc credits, GitHub link, "this is a static demo" disclosure.

---

## 6. Acceptance Criteria (Stage 3)

- [ ] β intro page renders; lede paragraph reads cleanly.
- [ ] World map renders in <1.5s; tenant footprint outlines are visible and accurate.
- [ ] France drilldown shows the 13-month escalating signal pattern; events are real and linked.
- [ ] At least 3 cascade cards render with real Carver trigger events.
- [ ] FATF cascade highlights ≥3 jurisdictions in Polymarket's operating footprint.
- [ ] Quarterly report renders all sections; watch list names 3 real jurisdictions with rationales.
- [ ] Pre-rendered Q2 2026 PDF artifact exists and is downloadable.
- [ ] Watch-list copy includes the "pattern-based projection, not prediction" hedge.
- [ ] Close page CTA links work.
- [ ] Carver leadership dry-run: scene 3 plays end-to-end in ≤5 minutes. The watch-list page produces the "I need to send this to our board" reaction.
- [ ] Mobile / tablet: world map zoom-pan works; quarterly report is readable in single-column reflow.

---

## 7. Open Questions (β-walkthrough-local)

| # | Question | Suggested resolution |
|---|---|---|
| BW1 | Does the Carver pull cover 13 months of France ANJ activity sufficiently to populate the retrospective? | Audit at Stage 0. ANJ is on the regulator allowlist; if direct ANJ coverage is sparse, supplement with EU-level events (EC, ESMA) referring to France. Document the gap honestly on the page footer. **Resolved (2026-05-20):** Carver corpus has 1,481 FR records spanning 2020-2026 with strong AMF + ESMA + EU coverage but no direct ANJ events. Stage 3 plan's Task 4 reframes the retrospective copy from "ANJ ban" to "escalating French regulatory pressure (AMF/ESMA-led perimeter action)". Footer on `/beta/heatmap/` discloses the ANJ gap. |
| BW2 | The "watch list" names *currently-active* jurisdictions. Which ones? | **Deferred until after Carver pull (decision recorded 2026-05-19).** Hand-pick during Stage 3 data prep based on what the Carver pull actually shows. Strong candidates from public reporting: Brazil (SECAP scrutiny), Mexico (recent tightening), India (always-imminent), Korea (gambling regulator activity), Australia (AUSTRAC posture). The selection must be defensible against current public data. Same deferral applies to the primary heat-map retrospective focus (France ANJ default; cascade-signal-only or multi-jurisdiction patterns as alternatives). |
| BW3 | Cascade hit-rate annotations ("31/39 members") — where does that number come from? | Computed once at data-prep time from historical Carver data. If the back-test fails for a rule (rate < 30%), don't ship that rule in the demo (per `future/40-beta-strategic-expansion.md` § 9). |
| BW4 | Q2 2026 report — what if Carver coverage starts later than Q2 2025 (limits comparison)? | Use whatever prior window is available for the delta calculations; add a footer note clarifying the window. If <6 months of prior data, replace delta-based pressure-rising/falling with absolute-volume rankings and a different framing. |
| BW5 | PDF artifact — produce via WeasyPrint at Stage 3, or hand-render once? | Hand-render once for the demo (using browser print-to-PDF on the HTML page). Stage-4 polish may add an actual WeasyPrint command if useful. Pre-rendered file lives in `site/static/samples/`. |
| BW6 | Privacy / political sensitivity of naming specific countries on a watch list? | All cited events are public. All cited regulators are public. The page framing is "based on signals already in the public record" — no insider claim. Defensible. Maintain `data/sources/watch-list-evidence.md`. |
| BW7 | Should the demo support clicking from a watch-list jurisdiction back into α's per-jurisdiction dashboard? | Yes — small "View in α dashboard" link per watch-list item. Closes the loop and shows the spine is shared across modules. |
