# Spec: γ — Listed-Asset Regulatory Risk

> **Status:** Draft, pending team review.
> **Strategy doc reference:** § 4.2.
> **Prerequisites:** [`10-data-spine.md`](10-data-spine.md), [`20-alpha-regulatory-risk-radar.md`](20-alpha-regulatory-risk-radar.md) (γ extends α's tickets table).

γ answers: **"For every contract on our platform, is a regulator about to do something that affects its settlement or pricing?"** It links spine events to the platform's listed contracts and surfaces the result to the listing-risk team.

---

## 1. Purpose & Buyer

- **Buyer of record:** Head of Listing / Head of Trading Risk at the prediction-market platform.
- **Primary users:** listing-team members, trading-risk analysts.
- **Use cases:**
  - **Pre-listing scan:** before a contract goes live, check whether the named entities have recent or pending regulatory activity that would move pricing or blow up settlement.
  - **Live monitoring:** every Carver event whose entities or `regulatory_source.name` intersect an active contract's resolution entities opens a listing-risk ticket.
  - **Contract-watch dashboard:** sorted view of active contracts by regulatory-heat score for morning trading-risk review.

---

## 2. In Scope / Out of Scope

**In scope:**
- Listed-contract catalog ingestion (API poll + CSV fallback) — schema and pipeline.
- Contract → entity parsing (deterministic + LLM-assisted).
- Pre-listing scan synchronous endpoint.
- Live event-linking pipeline (`contract_event_links`).
- Regulatory-heat scoring and materialization.
- Listing-risk tickets (extension of α's `tickets` table).
- Contract-watch dashboard.
- Alerting reusing spine notification dispatcher.

**Out of scope (V1):**
- Settlement-grade citation feed (that's a different product, Approach B in strategy doc § 8.3).
- Per-contract pricing impact prediction (no historical price data; would need a separate market-data integration).
- Auto-pause / auto-resolve recommendations for contracts (advisory only).

---

## 3. Data Model (γ-specific)

### 3.1 Extension to α's `tickets` table

```sql
ALTER TABLE tickets ADD COLUMN kind TEXT NOT NULL DEFAULT 'alpha_radar'
    CHECK (kind IN ('alpha_radar','gamma_listing_risk'));
ALTER TABLE tickets ADD COLUMN listed_contract_id UUID REFERENCES listed_contracts(id);

CREATE INDEX tickets_kind_idx              ON tickets(tenant_id, kind, status, priority DESC);
CREATE INDEX tickets_listed_contract_idx   ON tickets(tenant_id, listed_contract_id) WHERE status != 'closed';
```

A γ ticket is uniquely identified by `(filter_match_id, listed_contract_id)` — same event can fan out to multiple γ tickets if it touches multiple contracts.

Replace the original `UNIQUE (filter_match_id)` constraint with a unique index that handles the nullable `listed_contract_id`:

```sql
ALTER TABLE tickets DROP CONSTRAINT tickets_filter_match_id_key;

CREATE UNIQUE INDEX tickets_match_contract_unique ON tickets (
    filter_match_id,
    COALESCE(listed_contract_id, '00000000-0000-0000-0000-000000000000'::uuid)
);
```

(`UNIQUE` constraints in PostgreSQL can't reference expressions; a unique index can. The COALESCE preserves α's "one ticket per match" while letting γ create one per (match, contract) pair.)

### 3.2 Contract → event linking

```sql
CREATE TABLE contract_event_links (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    listed_contract_id  UUID NOT NULL REFERENCES listed_contracts(id),
    event_id            UUID NOT NULL REFERENCES regulatory_events(id),
    matched_entity      TEXT NOT NULL,                      -- canonical entity name that fired the link
    match_reason        TEXT NOT NULL CHECK (match_reason IN (
        'settlement_entity','regulatory_source','reg_reference','title_keyword'
    )),
    severity            INT NOT NULL CHECK (severity BETWEEN 1 AND 10),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (listed_contract_id, event_id, matched_entity, match_reason)
);

CREATE INDEX contract_event_links_contract_idx  ON contract_event_links(listed_contract_id, created_at DESC);
CREATE INDEX contract_event_links_event_idx     ON contract_event_links(event_id);

ALTER TABLE contract_event_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY contract_event_links_isolation ON contract_event_links
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

Severity derivation:
```python
severity = round((event.urgency_score * 0.5) + (event.impact_score * 0.5))
# Boost for direct-settlement-entity matches
if match_reason == 'settlement_entity':
    severity = min(10, severity + 2)
severity = max(1, min(10, severity))
```

### 3.3 Contract regulatory-heat score

Materialized hourly into `contract_heat`:

```sql
CREATE TABLE contract_heat (
    listed_contract_id  UUID PRIMARY KEY REFERENCES listed_contracts(id),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    heat_score          NUMERIC(8,3) NOT NULL,
    n_events_30d        INT NOT NULL,
    n_events_90d        INT NOT NULL,
    last_event_at       TIMESTAMPTZ,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX contract_heat_tenant_score_idx ON contract_heat(tenant_id, heat_score DESC);
ALTER TABLE contract_heat ENABLE ROW LEVEL SECURITY;
CREATE POLICY contract_heat_isolation ON contract_heat
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

Formula:
```python
heat_score = sum(
    link.severity * exp(-age_days / 14.0)
    for link in contract_event_links
    if link.contract_id == c and now - link.created_at < 90.days
)
```

### 3.4 Pre-listing scan history (for audit + caching)

```sql
CREATE TABLE pre_listing_scans (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    requested_by        UUID NOT NULL REFERENCES users(id),
    proposed_title      TEXT NOT NULL,
    proposed_criteria   TEXT NOT NULL,
    extracted_entities  TEXT[] NOT NULL,
    severity_score      INT NOT NULL,                    -- summary score 1-10
    summary             JSONB NOT NULL,                  -- full scan result
    listed_contract_id  UUID REFERENCES listed_contracts(id),  -- set if contract subsequently listed
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE pre_listing_scans ENABLE ROW LEVEL SECURITY;
CREATE POLICY pre_listing_scans_isolation ON pre_listing_scans
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

---

## 4. Contract → Entity Extraction

Same two-stage pattern as spine entity resolution (§ 6 of data-spine spec):

**Stage A — deterministic, in-process, <50ms:**
1. Tokenize title and resolution criteria.
2. Match tokens against:
   - Tenant's `entity_catalog_entries` (canonical names + aliases).
   - Carver `regulatory_source.name` global enum (CFTC, SEC, FCC, …).
   - A curated list of known prediction-market regulators (50 US state gambling commissions, ANJ, KSA, GRA, UKGC, MGA, etc., maintained in `app/data/known_regulators.yml`).
3. Return list of canonical entities + match reasons.

**Stage B — LLM-assisted, async, only for low-confidence stage-A results:**
- Triggered when Stage A finds <2 entities and the title length > 40 chars (heuristic for "looks specific but didn't match catalog").
- Claude Sonnet call with prompt: "Given this prediction-market contract title and resolution criteria, list the named regulators, companies, and government bodies whose actions would affect resolution." Returns JSON list.
- Output appended to `pre_listing_scans.extracted_entities`; admin queue surfaces low-confidence picks for triager confirmation.

Pre-listing scan endpoint always returns immediately with Stage-A results; Stage-B refinement is logged but doesn't block UX. Live monitoring uses Stage A only (latency-critical fan-out).

---

## 5. Listed-Contract Ingestion

### 5.1 API-pulled sources

ARQ scheduled jobs:

| Job | Schedule | Source |
|---|---|---|
| `gamma.sync_kalshi_contracts(tenant_id)` | hourly | Kalshi public market API (`/v1/markets`) |
| `gamma.sync_polymarket_contracts(tenant_id)` | hourly | Polymarket CLOB API (`/markets`) |

Per tenant, jobs are only enabled if `tenant_integrations` has `channel='listed_contracts_api'` with valid credentials (or for fully-public APIs, no credentials).

Each job:
1. Fetches the contract list page by page.
2. Upserts into `listed_contracts` keyed by `(tenant_id, external_id)`.
3. For new contracts: runs Stage-A entity extraction; populates `settlement_entities`.
4. Enqueues `gamma.backfill_links(contract_id)` for any new contract — links recent events that already match.

### 5.2 CSV fallback

`POST /api/v1/catalog/contracts/upload` (spine-defined). CSV columns: `external_id`, `title`, `resolution_criteria`, `listed_at`, `expires_at`, `status`, `settlement_entities` (semicolon-separated, optional — will run extraction if absent).

Re-running an upload upserts on `(tenant_id, external_id)`.

---

## 6. Live Event-Linking Pipeline

Extends the spine's per-event fan-out (data-spine spec § 7.4). After the existing `evaluate_filters(event_id)` step:

`gamma.link_event_to_contracts(event_id)`:

1. Load event.
2. Compute candidate entities: union of `event.entities` (post-resolution) + `event.regulatory_source_name` + names extracted from `event.reg_references` (regex over `<text (URL)>` strings).
3. For each tenant: query `listed_contracts WHERE status='active' AND settlement_entities && candidate_entities`.
4. For each match: INSERT into `contract_event_links` (idempotent on `(listed_contract_id, event_id, matched_entity, match_reason)`).
5. For each new link: enqueue `gamma.create_listing_risk_ticket(link_id)` if severity >= 5 (configurable per tenant).
6. Bump `contract_heat.heat_score` lazily (next hourly materialization recomputes).

---

## 7. APIs

All under `/api/v1/gamma`.

| Endpoint | Method | Role | Purpose |
|---|---|---|---|
| `/api/v1/gamma/pre-listing-scan` | POST | triager+ | Body: `{"title":"...","resolution_criteria":"..."}`. Synchronous; target p95 <2s. Returns extracted entities, recent matching events, severity score. |
| `/api/v1/gamma/pre-listing-scan/{id}` | GET | any | Retrieve a past scan. |
| `/api/v1/gamma/contracts` | GET | any | List contracts. Query: `status`, `min_heat`, `entity`, `sort` (`heat_desc`|`expiry_asc`|...), pagination. |
| `/api/v1/gamma/contracts/{id}` | GET | any | Contract detail + heat score + recent links. |
| `/api/v1/gamma/contracts/{id}/events` | GET | any | Linked events for contract, paginated, newest first. |
| `/api/v1/gamma/contracts/{id}/settlement-entities` | PATCH | admin | Override extracted entities. Triggers full backfill of `contract_event_links`. |
| `/api/v1/gamma/heat-snapshot` | GET | any | Materialized leaderboard: top-N contracts by heat. |
| `/api/v1/gamma/tickets` | GET | any | Same shape as `/api/v1/alpha/tickets` but filtered `kind='gamma_listing_risk'`. (Internally the same handler with a `kind` filter.) |

### 7.1 Pre-listing scan response shape

```jsonc
{
  "id": "uuid",
  "extracted_entities": [
    { "canonical_name": "CFTC", "match_reason": "deterministic", "confidence": 1.0 },
    { "canonical_name": "Tarek Mansour", "match_reason": "catalog", "confidence": 1.0 }
  ],
  "severity_score": 7,
  "severity_breakdown": {
    "n_recent_events": 14,
    "max_event_urgency": 9,
    "highlighted_events": [
      {
        "event_id": "uuid",
        "title": "CFTC Issues Cease and Desist…",
        "pub_date": "2026-05-10",
        "urgency_score": 9,
        "feed_url": "https://www.cftc.gov/..."
      }
      // ... up to 5
    ]
  },
  "warnings": [],   // e.g., "Low entity confidence — consider clarifying title"
  "created_at": "ISO"
}
```

---

## 8. Background Jobs

| Job | Schedule | Purpose |
|---|---|---|
| `gamma.sync_kalshi_contracts` | hourly | API poll |
| `gamma.sync_polymarket_contracts` | hourly | API poll |
| `gamma.backfill_links(contract_id)` | event-triggered (new contract) | Run last 90 days of events through link logic for the new contract. Bounded query — last 90 days × intersection of entities. |
| `gamma.link_event_to_contracts(event_id)` | event-triggered (ingested event) | (§ 6) |
| `gamma.create_listing_risk_ticket(link_id)` | event-triggered (new link, severity≥threshold) | Materialize a γ ticket. |
| `gamma.recompute_heat` | cron, hourly | Recompute `contract_heat` for all active contracts. |
| `gamma.expire_resolved_links` | cron, daily | Mark links to closed contracts read-only; don't re-recompute heat. |

---

## 9. UI Surfaces

### 9.1 Pre-listing scan tool

Route: `/gamma/scan`.

Layout (single-page form):
- Two textareas: "Contract title" and "Resolution criteria".
- "Run scan" button → POST, spinner, results in panel below.
- Result panel:
  - Severity badge (1–10 with color).
  - Extracted entities list with delete buttons (manual correction).
  - "Recent regulatory activity" list — collapsed by entity, expand to see events.
  - "Re-run with these entities" button if user manually edits entity list.
  - "Save this scan" → links to a (future) listed_contract once the platform creates it.

### 9.2 Contract-watch dashboard

Route: `/gamma/dashboard`.

Top: leaderboard table of active contracts.
Columns: heat-score sparkline (last 14 days), contract title (clickable), entities (chips), expiry, n_events_30d, last_event_at, open-tickets badge.

Default sort: heat_score DESC. Quick filters: heat ≥5 / ≥7 / ≥9, expires <30d, has-open-ticket.

### 9.3 Contract detail

Route: `/gamma/contracts/{id}`.

- Header: title, external_id, status, expiry, heat score (large), heat trend chart (line, last 90 days, daily).
- Entities section: editable list (admin only) of `settlement_entities`.
- Linked events: paginated, newest first, with severity badge per link and "Open ticket" CTA where one exists.
- Tickets: list of γ tickets on this contract.

### 9.4 γ inbox

Route: `/gamma/inbox`.

Shares α's inbox component, parameterized with `kind='gamma_listing_risk'`. Extra column: "Contract" (clickable → contract detail). Default sort: contract heat-score DESC, then ticket priority DESC.

---

## 10. Acceptance Criteria

γ live (M9 milestone) requires:

- [ ] Both design partners have ≥1 listed-contract catalog imported (API or CSV).
- [ ] Pre-listing scan: response p95 <2s for a 200-word title + criteria; entity extraction sample manually validated against 50 real Kalshi + Polymarket contract titles with ≥80% precision and recall on Stage A.
- [ ] Live linking: ingest a fixture event whose `entities` include a known settlement_entity → `contract_event_links` row created within 60s.
- [ ] γ ticket creation: severity-7 link → ticket appears in `/gamma/inbox` within 60s; Slack alert dispatched to listing-risk channel.
- [ ] Contract-watch dashboard: heat scores agree with hand-computed values on a fixture of 20 contracts × 30 events.
- [ ] Heat materialization cron runs hourly without lock contention; verified at 1000 contracts × 10k recent links.
- [ ] Admin override of `settlement_entities` triggers full backfill: 90 days × matching events re-link within 5 minutes for a contract with 100 candidate entities.
- [ ] RLS verified: tenant A cannot read tenant B's contracts, links, scans, or tickets.

---

## 11. Open Questions (γ-local)

| # | Question | Suggested resolution |
|---|---|---|
| G1 | Are public Kalshi / Polymarket APIs stable enough to rely on, or should we plan for breakage? | Wrap each in a small adapter module with a clear interface; on schema breakage, fall back to CSV ingestion + admin notification. Add contract tests with recorded fixtures. |
| G2 | Should γ also link historical (closed) contracts to events for audit, or only active? | Active only in V1. ε (roadmap) is where historical-contract dossiers live. |
| G3 | The `reg_references` field is a structured-ish list of `"<text (URL)>"`; do we trust the entity-name extraction from it? | Conservative: only use as a *weak signal* for `match_reason='reg_reference'` with severity capped at 5. Don't auto-create tickets from reg_reference matches in V1; surface them as advisory annotations on contract detail. |
| G4 | If two tenants list the same external_id (unlikely cross-platform but possible same-platform sub-orgs), should links be shared? | No. `listed_contracts` is tenant-scoped; cross-tenant sharing would violate isolation invariants. Re-evaluate only if a multi-org tenant case emerges. |
| G5 | Stage B (LLM-assisted entity extraction) — cost budget and human-review SLA? | Initial budget: $100/month for design-partner phase (Carver Anthropic account). Human review SLA on LLM-flagged scans: same-business-day. Tighten if cost/volume diverges. |
| G6 | Does Polymarket's UMA-oracle-based settlement change which entities should be tracked? | Yes — UMA voting addresses and key UMA contributors should be in the global known-regulators list. Coordinate with Polymarket design partner at M7. |
