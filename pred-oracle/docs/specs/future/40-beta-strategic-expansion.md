# Spec: β — Strategic Expansion Intelligence

> **Status:** Draft, pending team review.
> **Strategy doc reference:** § 4.3.
> **Prerequisites:** [`10-data-spine.md`](10-data-spine.md). β reuses the spine's event store and tenant catalogs but adds its own materializations and report generator.

β answers: **"Which jurisdictions are getting easier, harder, or imminently dangerous for our business?"** It's the longitudinal / aggregation read of the same data α and γ use point-in-time.

---

## 1. Purpose & Buyer

- **Buyer of record:** Head of International / Corp Dev. Also consumed by CEO and Board in quarterly review.
- **Primary users:** International team, Corp Dev, exec staff for the quarterly report.
- **Use cases:**
  - Interactive jurisdiction heat-map for ad-hoc analysis ("what's been happening in Brazil?").
  - Auto-drafted quarterly intelligence report — exportable as a board-meeting PDF.
  - Predictive cascade alerts — "FATF just issued guidance X; based on prior cascades, expect member-state action in N months."

---

## 2. In Scope / Out of Scope

**In scope:**
- Materialized aggregates over `regulatory_events` keyed by (jurisdiction, week, update_type, impacted_business_type).
- Heat-map UI tied to tenant's `jurisdictional_footprint`.
- Cascade-rule engine (rule-based in V1).
- Quarterly report generator (PDF via WeasyPrint).
- Trend-analysis APIs for downstream consumers (the platform's own systems via webhook/API).

**Out of scope (V1):**
- Learned cascade patterns (V2+ — requires more accrued history; see strategy § 7.3, § 9.3).
- Country-specific deep-dives beyond what `regulatory_events` carries (e.g., interpretive commentary, geopolitical context).
- Cross-tenant benchmarking ("how does Kalshi's exposure compare to Polymarket's").
- Predictive contract pricing (not in any V1 module).

---

## 3. Data Model (β-specific)

### 3.1 Materialized aggregate

```sql
CREATE MATERIALIZED VIEW jurisdiction_pressure_weekly AS
SELECT
    jurisdiction,
    date_trunc('week', pub_date)::date AS week_start,
    update_type,
    update_subtype,
    impacted_business_type,
    COUNT(*) AS event_count,
    AVG(urgency_score)::numeric(3,1) AS avg_urgency,
    AVG(impact_score)::numeric(3,1) AS avg_impact,
    MAX(urgency_score) AS max_urgency,
    (array_agg(id ORDER BY urgency_score DESC NULLS LAST))[1:10] AS top_event_ids
FROM regulatory_events,
     LATERAL unnest(COALESCE(jurisdictions, '{}'::text[])) AS jurisdiction,
     LATERAL unnest(COALESCE(impacted_business_types, '{}'::text[])) AS impacted_business_type
WHERE pub_date IS NOT NULL
GROUP BY 1, 2, 3, 4, 5;

CREATE UNIQUE INDEX jurisdiction_pressure_weekly_pk
    ON jurisdiction_pressure_weekly (jurisdiction, week_start, update_type, update_subtype, impacted_business_type);

CREATE INDEX jurisdiction_pressure_weekly_jur_idx
    ON jurisdiction_pressure_weekly (jurisdiction, week_start DESC);
```

Refresh: `REFRESH MATERIALIZED VIEW CONCURRENTLY jurisdiction_pressure_weekly` runs hourly via ARQ.

Tenant scoping happens at read time: heat-map APIs join `jurisdictional_footprint` to filter cells to jurisdictions in the tenant's footprint (operating + considering).

### 3.2 Cascade rules

```sql
CREATE TABLE cascade_rules (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL UNIQUE,
    description             TEXT NOT NULL,
    trigger_sources         TEXT[] NOT NULL,
    trigger_update_types    TEXT[],
    expected_followers      TEXT[] NOT NULL,    -- ISO jurisdiction codes
    follow_window_days      INT NOT NULL DEFAULT 365,
    rationale               TEXT,               -- analyst note, optional
    enabled                 BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Cascade rules are **global** (no `tenant_id`), curated by Pred-Oracle staff. Each tenant sees signals filtered against its own `jurisdictional_footprint`.

V1 seed rules (loaded from `app/data/cascade_rules.yml` on first migration):

- `fatf_member_states`: FATF guidance → all 39 FATF members likely action within 18 months.
- `iosco_member_jurisdictions`: IOSCO guidance → all IOSCO ordinary members within 24 months.
- `eu_member_state_anti_money_laundering`: EU AMLD → all 27 EU members within follow_window of effective_date.
- `prediction_market_state_cascade_us`: NV/NJ/MA/MD enforcement action → other states with similar gambling-statute structure within 12 months.

### 3.3 Cascade signals

```sql
CREATE TABLE cascade_signals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cascade_rule_id     UUID NOT NULL REFERENCES cascade_rules(id),
    trigger_event_id    UUID NOT NULL REFERENCES regulatory_events(id),
    expected_until      DATE NOT NULL,
    fired_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cascade_rule_id, trigger_event_id)
);

CREATE INDEX cascade_signals_expected_idx ON cascade_signals(expected_until);
```

Global table (no tenant_id); per-tenant relevance computed at read time by intersecting `cascade_rules.expected_followers` with `tenant.jurisdictional_footprint`.

### 3.4 Quarterly reports

```sql
CREATE TABLE quarterly_reports (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id),
    quarter                 TEXT NOT NULL,                          -- '2026-Q2'
    status                  TEXT NOT NULL CHECK (status IN ('draft','published','archived')),
    summary                 JSONB NOT NULL,                         -- structured content (see § 7.2)
    pdf_object_key          TEXT,                                   -- S3 / object-store key
    generated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at            TIMESTAMPTZ,
    published_by            UUID REFERENCES users(id),
    UNIQUE (tenant_id, quarter)
);

ALTER TABLE quarterly_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY quarterly_reports_isolation ON quarterly_reports
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

### 3.5 Saved jurisdictional views (optional)

Lets a user pin a heat-map configuration for one-click recall.

```sql
CREATE TABLE saved_heatmap_views (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    created_by          UUID NOT NULL REFERENCES users(id),
    name                TEXT NOT NULL,
    config              JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, created_by, name)
);

ALTER TABLE saved_heatmap_views ENABLE ROW LEVEL SECURITY;
CREATE POLICY saved_heatmap_views_isolation ON saved_heatmap_views
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

---

## 4. Cascade Detection

Runs as part of the spine's per-event fan-out (data-spine spec § 7.4). After filter evaluation:

`beta.detect_cascade_signals(event_id)`:

1. Load event.
2. For each enabled `cascade_rules` where `event.regulatory_source_name = ANY(trigger_sources)` AND (`trigger_update_types IS NULL OR event.update_type = ANY(trigger_update_types)`):
3. INSERT into `cascade_signals` (idempotent via UNIQUE).
4. For each tenant whose `jurisdictional_footprint` intersects `cascade_rules.expected_followers`:
   - Render a "cascade detected" Slack/email notification (digest-only by default; tenant can opt-in to real-time).
5. Cascade signals expire on `expected_until` (no action needed; reads filter by date).

---

## 5. APIs

All under `/api/v1/beta`.

| Endpoint | Method | Role | Purpose |
|---|---|---|---|
| `/api/v1/beta/heatmap` | GET | any | Query the materialized aggregate. Params: `from`, `to`, `tier`, `update_types[]`, `business_types[]`. Returns 2D grid: jurisdiction × update_type, cells = {count, avg_urgency, max_urgency}. Filters to tenant's footprint. |
| `/api/v1/beta/heatmap/{jurisdiction}` | GET | any | Drilldown: events for jurisdiction in window. Honors same query params. |
| `/api/v1/beta/trends/{jurisdiction}` | GET | any | Per-jurisdiction time series. Returns weekly counts + avg urgency over the window. |
| `/api/v1/beta/cascade-signals` | GET | any | Active signals where `expected_until > today` AND tenant's footprint intersects expected_followers. |
| `/api/v1/beta/reports` | GET | any | List tenant's quarterly reports. |
| `/api/v1/beta/reports/{quarter}` | GET | any | Get a report's structured content. |
| `/api/v1/beta/reports/{quarter}/pdf` | GET | any | Signed download URL for the rendered PDF. |
| `/api/v1/beta/reports/{quarter}/generate` | POST | admin | Manual trigger; idempotent (returns existing if already published). |
| `/api/v1/beta/saved-views` | GET, POST | any | CRUD saved heat-map views. |
| `/api/v1/staff/cascade-rules` | GET, POST, PATCH, DELETE | staff | Manage global cascade rules. |

### 5.1 Heatmap response shape

```jsonc
{
  "from": "2026-02-01",
  "to": "2026-05-01",
  "jurisdictions": [
    {
      "code": "US-CA",
      "tier": "domestic",
      "tenant_status": "operating",
      "cells": {
        "enforcement":     { "count": 4, "avg_urgency": 7.2, "max_urgency": 9, "top_event_ids": ["uuid","uuid"] },
        "proposed rule":   { "count": 2, "avg_urgency": 5.1, "max_urgency": 6, "top_event_ids": ["uuid"] }
      }
    },
    { "code": "FR", "tier": "international", "tenant_status": "closed", "cells": { ... } }
  ],
  "cascade_signals_summary": {
    "active_count": 3,
    "imminent_count": 1     // expected_until within next 90 days
  }
}
```

---

## 6. Background Jobs

| Job | Schedule | Purpose |
|---|---|---|
| `beta.refresh_aggregate` | cron, hourly @ :05 | `REFRESH MATERIALIZED VIEW CONCURRENTLY jurisdiction_pressure_weekly`. |
| `beta.detect_cascade_signals` | event-triggered | (§ 4) |
| `beta.generate_quarterly_report(tenant_id, quarter)` | cron, daily; fires per tenant on day-3 of each new quarter | Builds the report; idempotent. |
| `beta.dispatch_cascade_digest` | cron, daily @ 14:00 UTC | Per-tenant digest of cascade signals matching footprint, fired in last 24h. |

---

## 7. Quarterly Report Generator

### 7.1 Structure

The report is structured as `quarterly_reports.summary` JSONB:

```jsonc
{
  "quarter": "2026-Q2",
  "tenant": { "id": "uuid", "display_name": "..." },
  "headline_stats": {
    "events_in_window": 412,
    "jurisdictions_with_activity": 38,
    "high_urgency_events": 47,
    "active_cascade_signals": 3
  },
  "pressure_up": [
    {
      "jurisdiction": "US-CA",
      "delta_events_vs_prior_quarter": 12,
      "delta_avg_urgency": 1.4,
      "narrative": "California state-level enforcement activity escalated...",
      "top_events": [{ "event_id": "uuid", "title": "...", "feed_url": "..." }]
    }
    // up to 10
  ],
  "pressure_down": [ /* up to 5 */ ],
  "watch_list": [ /* up to 3 — derived from cascade_signals where expected_until in next quarter */ ],
  "appendix": {
    "all_active_cascade_signals": [...],
    "method_notes": "Counts derived from Carver-ingested regulatory updates..."
  }
}
```

### 7.2 Pressure-up / down derivation

For each jurisdiction in tenant's footprint:
- `delta_events = events_this_quarter - events_prior_quarter`
- `delta_avg_urgency = avg_urgency_this_quarter - avg_urgency_prior_quarter`
- Composite rank: `delta_events * 0.5 + delta_avg_urgency * 5` (urgency weighted higher).
- Top 10 ranks → `pressure_up`. Bottom 5 (most negative) → `pressure_down`.

Narratives use a templated prose generator (Jinja, no LLM in V1) that picks a sentence pattern per jurisdiction based on which dimension drove the rank (more events vs higher urgency vs new update_types appearing).

### 7.3 PDF rendering

WeasyPrint renders `templates/beta/quarterly_report.html.j2` to PDF:
- Cover page: tenant logo + quarter + generated date.
- TOC.
- Headline stats (large number tiles).
- Pressure-up section: one page per jurisdiction with chart (ECharts SVG embedded), narrative, top events.
- Pressure-down section: condensed table.
- Watch-list section: per-cascade with expected timing.
- Appendix.
- Footer: "Generated by Pred-Oracle; sources: Carver entry_annotation pipeline."

Output stored in S3 (or compatible object store) at `s3://pred-oracle-reports/{tenant_id}/{quarter}.pdf`. Pre-signed URL returned on download.

---

## 8. UI Surfaces

### 8.1 Heat-map dashboard

Route: `/beta/heatmap`.

Top controls:
- Date window (default last 90 days, custom range).
- Tier multi-select (all, US federal, US state, international).
- Update-type multi-select.
- Business-type multi-select.
- "Save view" button.

Body:
- **Choropleth world map** (D3.js or ECharts geo-map): country fill = total event count in window; click → jurisdiction drilldown.
- **US states map** below world: US state fills using `US-XX` codes; same drilldown semantics.
- **Heat-table** alongside (jurisdictions × update_type, sortable cells).

Drilldown pane (right slide-in):
- Header: jurisdiction code, tenant status badge, weekly trend sparkline.
- Tabs: Events list / Cascade signals / Saved filters touching this jurisdiction.
- Events list: paginated, newest first, link to event detail.

### 8.2 Cascade signals

Route: `/beta/cascades`.

Table:
- Cascade rule name
- Trigger event (clickable)
- Expected followers (chips, tenant-footprint jurisdictions highlighted)
- Time-to-expected-window
- Cascade rationale (analyst note)

### 8.3 Quarterly report

Route: `/beta/reports/{quarter}`.

- Read-only render of the JSONB summary (same layout as the PDF, but interactive).
- "Download PDF" button.
- Admin: "Regenerate" + "Publish" buttons.

### 8.4 Saved heat-map views

Route: `/beta/saved-views`. Simple list with rename / delete / "set as default" actions.

---

## 9. Acceptance Criteria

β live (M12 milestone) requires:

- [ ] `jurisdiction_pressure_weekly` materialized view refreshes hourly without lock contention; verified at >100k event rows.
- [ ] Heat-map API: response p95 <500ms for a tenant's full footprint over a 365-day window.
- [ ] World map and US states map render in <1.5s with footprint of 50 jurisdictions and 12 weeks of data.
- [ ] Cascade-rule firing: ingest a FATF guidance event, see `cascade_signals` rows materialize for all FATF member jurisdictions in tenant's footprint, and a digest email at the next scheduled run.
- [ ] Quarterly report generator: produces a valid PDF for both design partners for 2026-Q2 within 60s; manually reviewed by Head of International for one partner.
- [ ] Pressure-up/down narratives: 100 random tenant-quarter combinations yield narratives with no missing-data placeholders.
- [ ] RLS: tenant A cannot access tenant B's `quarterly_reports` or `saved_heatmap_views`.
- [ ] Predictive cascade accuracy (V1 calibration): for each V1 cascade rule, manually back-check the last 24 months — if the historical hit-rate is <30%, mark the rule `enabled=FALSE` and flag for redesign.

---

## 10. Open Questions (β-local)

| # | Question | Suggested resolution |
|---|---|---|
| B1 | Are V1 cascade rules accurate enough to push to customers? | Run § 9 back-test before enabling each rule. Default to disabled if hit-rate <30%; surface to tenant only if confidence ≥0.5. |
| B2 | Should the quarterly report include a section on contracts likely affected (cross-module with γ)? | Yes — small "γ touchpoints" sidebar listing top-5 active contracts with rising heat scores in tenant's footprint. Render only if γ is enabled for tenant. |
| B3 | What about jurisdictions outside the tenant's footprint that they may want to enter? | Add a "frontier watch" section to the quarterly report: top 5 currently-`considering` jurisdictions ranked by pressure trends. Source from `jurisdictional_footprint.status='considering'`. |
| B4 | Should heat-map cells link directly to filters in α? | Yes — "Add to triage" button on drilldown creates a saved filter scoped to the cell's jurisdiction + update_type and tags it `is_triage_source=TRUE`. Useful conversion path: from analytics into operational triage. |
| B5 | The strategy doc mentions "predictive cascades learned from historical patterns once enough data accrues" — what's the data threshold? | Defer to V2 planning. Heuristic: ≥3 full cycles per cascade pattern (so ~36+ months of accrued history for "annual cycle" rules). Track in `cascade_rules` metadata. |
| B6 | Storage cost of materialized view? | Estimated <10MB for 50 jurisdictions × 5 update_types × 5 business_types × 156 weeks (3 years) ≈ 200k rows. Acceptable indefinitely; partitioning unnecessary in V1. |
| B7 | Should we run a "shadow" β internally before customer ship? | Yes — generate one quarterly report internally at M9 (using accrued spine data) for Carver leadership; iterate before exposing to design partners at M12. |
