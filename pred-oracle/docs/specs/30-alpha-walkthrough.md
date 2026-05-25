# α Scene Walkthrough — "The GC's Monday Morning"

> **Stage 1 deliverable.** First scene in the demo. Sets the protagonist and the narrative posture for the rest of the walkthrough.
>
> **Prerequisites:** Stage 0 complete ([`10-data-prep.md`](10-data-prep.md), [`20-site-build.md`](20-site-build.md)).

---

## 1. Narrative

**Protagonist:** "Sara Chen," GC at a Kalshi-class platform (fictional name; clearly labelled). The viewer steps into her role.

**Setting:** Monday morning, 9:00 AM. Sara opens Pred-Oracle. Three days of regulatory activity accumulated over the weekend.

**Beats:**

1. **The inbox.** Sara sees prioritized tickets ranked by combined urgency × impact. One is unmistakably "act today" — the wow moment. Several are "this week." Several are "informational."
2. **The drill-down.** Sara clicks the top item — a real recent enforcement signal against the platform — and sees Carver's structured annotation rendered cleanly: source, jurisdiction, effective date, penalties, what changed, why it matters. Primary-source link goes to the actual regulator's page.
3. **The pattern.** Sara opens the per-jurisdiction dashboard. The states currently targeting prediction markets light up. She sees that pressure is escalating across a cluster of states with similar statute structure.
4. **The handoff.** Sara generates an audit export for outside counsel. The preview shows what the PDF will look like.

**Time on scene:** ~4 minutes.

**Tone:** professional, dry, no marketing copy. The product speaks through the data.

---

## 2. Page-by-Page

### 2.1 α Intro / Inbox

- **Route:** `/alpha/` (renders as `alpha/index.html`).
- **Template:** `build/templates/alpha/inbox.html`.
- **Data slice:** `build/page_data/alpha/inbox.json` (per [`10-data-prep.md`](10-data-prep.md) § 4.1).

**Layout (top to bottom):**

1. **Scene framing strip** (full-width banner).
   - Left: scene number "1 / 3" and breadcrumb.
   - Center: "Monday, 9:00 AM. You are **Sara Chen**, General Counsel. Three days of regulatory activity hit while you were offline."
   - Right: "Next: Drill into ticket →" disabled until the visitor clicks a ticket OR a "Skip to dashboard" link.
2. **Inbox header.**
   - Title: "Regulatory triage queue".
   - Count: "15 active items · 3 above your paging threshold (8)".
   - Inert filter chips (visual only — no JS): Status [New, Acknowledged, In Review, Drafted, Closed]; Assignee [All / Me]; Priority slider.
3. **Inbox table.**
   - Columns: Priority (color-coded badge 1–10) · Title · Source agency · Jurisdictions (chips) · Status · Assignee avatar · Due date · Created (relative).
   - 15 rows from `inbox.json`, default sort: `status='new'` first, then `priority DESC`, then `created_at DESC`.
   - Row click → `/alpha/tickets/{id}/`.
   - Each row's title is a real Carver event title (no rewording).
4. **Right-rail explainer** (collapsible, default open):
   - Heading: "How this works".
   - Body: "Every row is a real regulatory event ingested by Carver's annotation pipeline, scored for urgency and impact, then matched against this platform's saved filters. Click into any item to see the underlying structured data."
   - Small footer line: *"Comments, assignees, and status transitions on the next page are synthetic demo data."*

**Wow moment on this page:** the top row. Its title should be unmistakably "act today" — a state cease-and-desist, an active CFTC enforcement action against a competitor, or a fresh federal court ruling. Selected manually from `data/carver-events.json` during data-prep.

### 2.2 Ticket Detail

- **Route:** `/alpha/tickets/{id}/`.
- **Template:** `build/templates/alpha/ticket_detail.html`.
- **Data slice:** `build/page_data/alpha/tickets/{id}.json`.

**Five tickets are pre-rendered** — IDs picked from the inbox during data prep. The "wow" ticket is one of them; the other four are typical-priority items to make the inbox feel dense.

**Layout (two-pane):**

- **Left pane (60%) — event facts:**
  - Title (Carver `metadata.title`).
  - Source bar: regulator name, division, jurisdiction tier, jurisdiction chips, primary-source link with regulator favicon.
  - Date strip: pub date · effective date · compliance date · comment deadline (omit any that are null).
  - **What changed** — Carver's `impact_summary.what_changed`.
  - **Why it matters** — Carver's `impact_summary.why_it_matters`.
  - **Key requirements** — bulleted list from `impact_summary.key_requirements`.
  - **Penalties / consequences** — bulleted list from `penalties_consequences`.
  - **Regulatory references** — collapsed section with `reg_references.statutes`, `.rules`, `.precedents`, `.past_release`, all clickable.
  - **Entities mentioned** — chips from `entities`, with tenant-catalog entries highlighted.
  - **Raw annotation** — collapsed `<details>` with the full Carver JSON for credibility.

- **Right pane (40%) — workflow:**
  - **Urgency & impact** badges with the Carver scores.
  - **Priority** large number.
  - **Status** dropdown showing valid transitions (visual only — clicking does nothing in the demo, with a tooltip "Production deployment writes the transition to the audit log").
  - **Assignee** card (Sara Chen avatar).
  - **Due date** with overdue-color if past.
  - **Status timeline** — 2-3 synthetic transitions on a vertical timeline. Marked with a "demo data" badge.
  - **Comment thread** — 2-3 synthetic comments between Sara and a fictional junior counsel. Marked with the same badge. Includes one @mention to make the workflow feel real.

**Wow moment on this page (the top-priority ticket):** the Carver annotation is *richer* than what Sara could have found via Google Alerts in the same time. She sees the agency division, the effective date, the cross-references to past releases, the penalty schedule, *and* the structured "why it matters" pre-written — all without leaving the page. The right pane shows that this was assigned and triaged in a workflow, not lost in a Slack channel.

### 2.3 Per-Jurisdiction Dashboard

- **Route:** `/alpha/dashboard/`.
- **Template:** `build/templates/alpha/dashboard.html`.
- **Data slice:** `build/page_data/alpha/dashboard.json`.

**Layout:**

1. **Header:** "Where's the pressure?" subtitle: "Activity by jurisdiction in the last 90 days, scoped to prediction-market-relevant updates."
2. **US states choropleth** (ECharts geo-map).
   - State fill = `count` of in-scope events.
   - Tooltip on hover: state name, count, max urgency in window.
   - Click state → drilldown panel (right-side slide-in) listing the events for that state with links into ticket detail pages.
3. **Top-10 states table** below the map: rank, state, count, avg urgency, max urgency, "view tickets" link.
4. **Update-type bar chart** at right: count by `update_type` (enforcement, proposed rule, final rule, advisory, guidance), filterable by clicking a bar.
5. **International strip** at bottom: a horizontal list of international jurisdictions with non-zero activity, sorted by count.

**Wow moment:** the choropleth lights up a *cluster* of states that the viewer can name (NV, NJ, MD, MA, OH, MT, etc. — the real Kalshi state-action geography). It's the same picture as the headlines, but on one screen.

### 2.4 Audit Export Preview

- **Route:** `/alpha/audit-export/`.
- **Template:** `build/templates/alpha/audit_export.html`.
- **Data slice:** none (static demo page).

**Layout:**

1. **Header:** "Audit-log export — Q2 2026".
2. **Description paragraph:** "Every status transition and triage decision is recorded for CFTC compliance, SOC2 audit, and litigation discovery. Sample below: tickets resolved in the demo's pre-loaded snapshot."
3. **Sample table** (~10 rows from the simulated transition history across the 5 ticket detail pages): timestamp · ticket title · transition · transitioned-by · note.
4. **"What you'd download"** card with a screenshot-quality preview of a 1-page audit-PDF. Optionally a "View sample PDF" link → a static PDF artifact in `site/static/`.
5. **CTA strip:** "Next scene: Listing risk →" linking to `/gamma/`.

**Wow moment:** less a moment, more a relief — Sara doesn't need to manually log her triage decisions; the audit trail emerges from the workflow itself. Print-ready, downloadable, defensible.

---

## 3. Copy & Tone

- All headings and microcopy are **plain professional English**. No "AI-powered", no "synergy", no superlatives.
- Real events are described in Carver's own language (annotation fields go to the page verbatim).
- Synthetic content (comments, assignees, status transitions) carries the `_components/demo_badge.html` mark.
- Personal names of fictional personas have a small "(illustrative)" subscript on first appearance per scene.
- Real names of public figures (regulators, executives surfaced in entity chips) are *not* labeled illustrative — they're public.

---

## 4. Interaction Details

| Interaction | Behavior |
|---|---|
| Click row in inbox | Navigate to `/alpha/tickets/{id}/`. |
| Click "Status" dropdown on ticket detail | Show valid transitions; clicking one shows a tooltip "Production deployment writes this transition to the audit log." Then resets. |
| Click filter chip on inbox | Highlight chip visually only; no list filtering (it's a static page). Tooltip: "Filtering live in production." |
| Click state on dashboard choropleth | Slide-in panel with that state's event list; close button returns map. |
| Click "view tickets" in top-10 table | Anchor-jump back to inbox with that state's rows highlighted via fragment. |
| Hover ticket title | Show abridged Carver summary as tooltip. |
| Click "View sample PDF" | Open `site/static/samples/audit-export-sample.pdf` in a new tab. |

No JS state persistence; every page is fresh-loaded.

---

## 5. Acceptance Criteria (Stage 1)

- [ ] All four α pages render with no runtime errors and no console warnings.
- [ ] The inbox top item is a *real* recent event (verified against `data/carver-events.json` manually); the rest of the 15 entries are also real.
- [ ] Five ticket-detail pages exist and render their full Carver payload. Each includes ≥3 of: `what_changed`, `why_it_matters`, `key_requirements`, `penalties_consequences`, `reg_references`.
- [ ] Synthetic comments / transitions display the demo-data badge. No badge-less synthetic content escapes.
- [ ] US-state choropleth renders in <1.5s; tooltips and click drilldown work in Chrome / Firefox / Safari.
- [ ] Top-10 table counts agree with the data-slice JSON (no off-by-one).
- [ ] Audit-export preview includes a clickable sample PDF (or a clear "preview only" notice if PDF is deferred to Stage 4 polish).
- [ ] "Next scene" CTA on `/alpha/audit-export/` navigates to `/gamma/` (which is a placeholder until Stage 2 ships).
- [ ] Carver leadership dry-run: a friendly internal viewer can play scene 1 end-to-end in ≤4 minutes and articulates one "wow" without prompting.
- [ ] Mobile / tablet: inbox table reflows to a card list under 768px; ticket detail two-pane collapses to single-column.

---

## 6. Open Questions (α-walkthrough-local)

| # | Question | Suggested resolution |
|---|---|---|
| AW1 | Which real event is the "top-priority" wow moment? | Pick during data-prep after seeing the actual Carver pull. Candidate criteria: (a) urgency_score ≥ 8, (b) recent (<60 days from build date), (c) names a US state regulator or CFTC, (d) the prospect would recognize the event from news. Document the choice in `data/wow-moments.md`. |
| AW2 | Five ticket-detail pages — are they enough? | Probably. If a demo reviewer hits "view ticket" on a row that doesn't have a detail page, route to a graceful "details available in production" stub. |
| AW3 | Should the inbox include γ-flagged tickets (the kind=`gamma_listing_risk` extension)? | No in Stage 1. Keep α purely α-flagged; γ scene introduces listing-risk tickets in their own context. |
| AW4 | Persona name "Sara Chen" — okay or pick something else? | Names are placeholders. Pick a name the Carver team is comfortable with (avoid resembling actual employees of any prospect). Final choice in Stage 4 polish. |
| AW5 | Should we show actual platform logos (Kalshi / Polymarket) on the page chrome? | No on chrome — keeps the demo platform-agnostic in framing. Yes inside data (e.g., entity chips). |
| AW6 | What if Carver has zero events for some weeks in the 90-day dashboard window? | Display the empty buckets transparently — gaps in coverage are honest. Add a footer note: *"Coverage of state-level US gambling regulators is in active expansion; see Carver coverage status."* |
