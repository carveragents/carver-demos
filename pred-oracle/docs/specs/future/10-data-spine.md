# Spec: Shared Data Spine

> **Status:** Draft, pending team review.
> **Prerequisite for:** every other V1 module.
> **Strategy doc reference:** § 5 (Shared Data Spine), § 3 (Carver field schema).

The data spine is the platform that all three V1 modules share. This spec defines its components, schema, APIs, and operational invariants.

---

## 1. Components Overview

```
   ┌──────────────────────┐
   │   Carver entry_      │
   │   annotation         │       (external producer, sibling repo)
   │   workflow           │
   └──────────┬───────────┘
              │  HTTP push (HMAC-signed)
              ▼
   ┌──────────────────────┐
   │  Ingestion API       │  ───►  regulatory_events (raw + projected fields)
   └──────────┬───────────┘
              │  fan-out (ARQ jobs)
              ▼
   ┌──────────────────────┐
   │  Filter evaluator    │  ───►  filter_matches
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │  Notification        │  ───►  Slack / email / SMS / outbound webhook
   │  dispatcher          │
   └──────────────────────┘

   (Customer catalogs feed entity-resolution, filter evaluation, and module-specific dashboards)
   (Audit log records every state-changing action)
```

Spine subsystems:

1. **Tenancy + RBAC + auth** (§ 2)
2. **Carver ingestion** (§ 3)
3. **Event store** (§ 4)
4. **Customer catalogs** (§ 5)
5. **Entity resolution** (§ 6)
6. **Filter engine** (§ 7)
7. **Notification dispatcher** (§ 8)
8. **Outbound webhook delivery** (§ 9)
9. **Audit log** (§ 10)
10. **Admin APIs** (§ 11)

---

## 2. Tenancy, RBAC, and Auth

### 2.1 Tenants

```sql
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,            -- e.g. 'kalshi', 'polymarket'
    display_name    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',  -- active | suspended | onboarding
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 2.2 Users

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    email           TEXT NOT NULL,
    display_name    TEXT,
    role            TEXT NOT NULL CHECK (role IN ('admin','triager','viewer')),
    sso_subject     TEXT,                            -- OIDC `sub` claim
    sso_provider    TEXT,                            -- 'okta' | 'auth0' | 'google' | 'entra' | 'local'
    password_hash   TEXT,                            -- argon2, only for 'local' provider
    status          TEXT NOT NULL DEFAULT 'active',  -- active | invited | disabled
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email)
);

CREATE INDEX users_tenant_id_idx ON users(tenant_id);
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

**Pred-Oracle staff** are stored in a separate table `staff_users` (no tenant_id), with explicit `impersonate(tenant_id)` capability — every impersonation writes an `audit_log` row.

### 2.3 Auth flow

- **SSO path:** OIDC authorization-code flow via `Authlib`. Tenant admin configures the IdP discovery URL + client credentials at onboarding. `sso_subject` joins external IdP identity to Pred-Oracle user.
- **Local path:** Argon2-hashed password. Reserved for design-partner bootstrap only; not exposed in normal sales motion.
- **Session:** signed cookie containing `user_id` + `tenant_id`. Server-side session store in Redis with 12h sliding expiry; refresh on activity.

### 2.4 Per-request middleware

```python
# Pseudocode of FastAPI dependency
async def with_tenant_context(request: Request, db: AsyncSession):
    user = await load_session_user(request)
    request.state.user = user
    request.state.tenant_id = user.tenant_id
    await db.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": str(user.tenant_id)})
```

The `SET LOCAL` issues a Postgres session-variable scoped to the transaction. All subsequent queries on this connection are filtered by RLS policies referencing `current_setting('app.current_tenant')`.

### 2.5 RBAC enforcement

Two layers:
- **Route-level:** FastAPI dependency `require_role(*roles)` rejects requests where `user.role` isn't permitted.
- **Action-level (RLS):** Postgres RLS policies on write paths additionally check `current_setting('app.current_role')` for sensitive tables.

---

## 3. Carver Ingestion

### 3.1 Source contract

Carver's `entry_annotation` workflow produces structured JSON per regulatory entry (full schema in strategy doc Appendix A). Each entry has a stable `carver_id` (assigned by the upstream pipeline).

### 3.2 Transport: HTTP push (V1)

Pred-Oracle exposes:

```
POST /internal/ingest/carver
Authorization: HMAC <signature>
Content-Type: application/json

{
  "carver_id": "<stable id from upstream>",
  "payload": { /* full Carver annotation JSON */ }
}
```

- **Auth:** HMAC-SHA256 over the canonical request body with a shared secret stored in `secrets/carver_hmac` (or AWS Secrets Manager).
- **Idempotency:** `carver_id` UNIQUE on `regulatory_events`. Duplicate POSTs return `200 OK` with `{"ingested": false, "reason": "duplicate"}`.
- **Backpressure:** Reject `429` if Redis queue depth exceeds 10× normal; Carver retries with backoff.

**V2 alternative:** Carver-side outbox table polled by Pred-Oracle. Defer; HTTP push is simpler and adequate at expected throughput (hundreds of events/day, not thousands/second).

### 3.3 Ingestion handler responsibilities

1. Verify HMAC.
2. Insert row into `regulatory_events` (raw payload + projected fields — see § 4).
3. Enqueue `evaluate_filters(event_id)` job in ARQ.
4. Return 200/duplicate response.

The handler is fully synchronous up to step 3; fan-out happens asynchronously.

---

## 4. Event Store

### 4.1 Schema

```sql
CREATE TABLE regulatory_events (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    carver_id                   TEXT UNIQUE NOT NULL,
    ingested_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Projected fields from Carver payload (for fast filtering)
    title                       TEXT,
    summary                     TEXT,
    feed_url                    TEXT,
    pub_date                    DATE,
    update_type                 TEXT,
    update_subtype              TEXT,
    regulatory_source_name      TEXT,
    jurisdiction_tier           TEXT,
    jurisdictions               TEXT[],   -- ISO codes from impacted_business.jurisdiction
    impacted_business_types     TEXT[],
    impacted_business_industries TEXT[],
    entities                    TEXT[],   -- raw (un-resolved) entity list from Carver
    urgency_score               NUMERIC(3,1),
    impact_score                NUMERIC(3,1),
    relevance_score             NUMERIC(3,1),
    effective_date              DATE,
    compliance_date             DATE,
    comment_deadline            DATE,

    -- Full annotation for module-specific reads
    payload                     JSONB NOT NULL
);

CREATE INDEX regulatory_events_pub_date_idx       ON regulatory_events(pub_date DESC);
CREATE INDEX regulatory_events_update_type_idx    ON regulatory_events(update_type);
CREATE INDEX regulatory_events_jurisdictions_gin  ON regulatory_events USING GIN(jurisdictions);
CREATE INDEX regulatory_events_entities_gin       ON regulatory_events USING GIN(entities);
CREATE INDEX regulatory_events_ibtypes_gin        ON regulatory_events USING GIN(impacted_business_types);
CREATE INDEX regulatory_events_urgency_idx        ON regulatory_events(urgency_score DESC);
CREATE INDEX regulatory_events_payload_gin        ON regulatory_events USING GIN(payload jsonb_path_ops);
```

`regulatory_events` is **global** — no `tenant_id`. Tenant scoping happens at `filter_matches` (§ 7.3) and at module read paths.

### 4.2 Projection ETL

The projection from Carver payload → typed columns runs inside the ingestion handler. Mapping table:

| Pred-Oracle column | Carver path | Notes |
|---|---|---|
| `carver_id` | (request top-level) | Required, unique. |
| `title` | `metadata.title` | |
| `summary` | `metadata.summary` | |
| `feed_url` | `metadata.feed_url` | |
| `pub_date` | `critical_dates.pub_date_content` | ISO parse; tolerant of partial dates. |
| `update_type` | `update_type` | Stored verbatim; enum-validated in filter engine. |
| `update_subtype` | `update_subtype` | |
| `regulatory_source_name` | `regulatory_source.name` | |
| `jurisdiction_tier` | `jurisdiction_tier.label` | |
| `jurisdictions` | `impacted_business.jurisdiction` | ISO codes array. |
| `impacted_business_types` | `impacted_business.type` | |
| `impacted_business_industries` | `impacted_business.industry` | |
| `entities` | `entities` | Raw list; resolved at filter time via § 6. |
| `urgency_score` | `scores.urgency.score` | |
| `impact_score` | `scores.impact.score` | |
| `relevance_score` | `scores.relevance.score` | |
| `effective_date` | `critical_dates.effective_date` | |
| `compliance_date` | `critical_dates.compliance_date` | |
| `comment_deadline` | `critical_dates.comment_deadline` | |
| `payload` | (whole object) | Source of truth for module-specific reads. |

Date parsing: Hijri calendar dates from `critical_dates.pub_date_calendar=='islamic'` are converted to Gregorian via `convertdate.islamic`.

### 4.3 Reprocessing

If Carver re-emits an entry with `carver_id` matching an existing row (e.g., upstream correction), the ingestion handler does an `INSERT ... ON CONFLICT (carver_id) DO UPDATE` and re-enqueues filter evaluation. Audit-log row records the update.

---

## 5. Customer Catalogs

Three per-tenant catalogs.

### 5.1 Entity catalog (used by α and γ)

```sql
CREATE TABLE entity_catalog_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    canonical_name  TEXT NOT NULL,
    aliases         TEXT[] NOT NULL DEFAULT '{}',
    role            TEXT NOT NULL CHECK (role IN ('self','staff','competitor','subsidiary','regulator','other')),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, canonical_name)
);

CREATE INDEX entity_catalog_tenant_idx ON entity_catalog_entries(tenant_id);
ALTER TABLE entity_catalog_entries ENABLE ROW LEVEL SECURITY;
CREATE POLICY entity_catalog_tenant_isolation ON entity_catalog_entries
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

Ingestion: CSV upload via admin UI, or `POST /api/catalog/entities` (auth: `admin`).

### 5.2 Listed-contract catalog (used by γ)

```sql
CREATE TABLE listed_contracts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id),
    external_id             TEXT NOT NULL,                            -- platform's contract id
    title                   TEXT NOT NULL,
    resolution_criteria     TEXT,
    settlement_entities     TEXT[] NOT NULL DEFAULT '{}',             -- resolved against entity catalog
    listed_at               TIMESTAMPTZ,
    expires_at              TIMESTAMPTZ,
    status                  TEXT NOT NULL CHECK (status IN ('active','resolved','cancelled')),
    source                  TEXT NOT NULL,                            -- 'api' | 'csv' | 'manual'
    last_synced_at          TIMESTAMPTZ,
    payload                 JSONB,                                    -- raw upstream record
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, external_id)
);

CREATE INDEX listed_contracts_tenant_idx       ON listed_contracts(tenant_id);
CREATE INDEX listed_contracts_settle_gin       ON listed_contracts USING GIN(settlement_entities);
ALTER TABLE listed_contracts ENABLE ROW LEVEL SECURITY;
CREATE POLICY listed_contracts_tenant_isolation ON listed_contracts
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

Ingestion: scheduled ARQ job polls Kalshi / Polymarket public APIs (see overview § 6 Q2) hourly; falls back to CSV upload.

### 5.3 Jurisdictional footprint (used by α and β)

```sql
CREATE TABLE jurisdictional_footprint (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    jurisdiction_code   TEXT NOT NULL,                                -- ISO 3166-1 alpha-2; 'US-CA' for US states
    status              TEXT NOT NULL CHECK (status IN ('operating','considering','closed','excluded')),
    notes               TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, jurisdiction_code)
);

ALTER TABLE jurisdictional_footprint ENABLE ROW LEVEL SECURITY;
CREATE POLICY jurisdictional_footprint_tenant_isolation ON jurisdictional_footprint
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

Ingestion: admin UI CSV upload + `POST /api/catalog/jurisdictions`.

---

## 6. Entity Resolution

The Carver `entities` field is a per-document deduplicated list, but it is NOT cross-document canonicalized. "Tarek Mansour", "T. Mansour", and "Kalshi CEO" can appear separately. Pred-Oracle resolves them to canonical names so filter expressions over `entity_catalog_entries` actually fire reliably.

### 6.1 Two-stage resolution

**Stage A — deterministic (fast path, in ingestion handler):**

For each raw entity string `e` in the Carver event:
1. Lookup `e` in a global `entity_aliases` table → canonical_name if hit.
2. Else lookup `e` (lowercased, normalized whitespace) against all tenants' `entity_catalog_entries.aliases` array.
3. Else leave `e` as-is and emit a `unresolved_entity` row for stage B.

**Stage B — LLM-assisted (offline, batched hourly):**

ARQ job `resolve_unresolved_entities` batches unresolved entities and asks an LLM (Claude Sonnet) to propose canonical mappings against the global alias table and tenant entity catalogs. Each proposal is written to `entity_alias_proposals` with confidence; admin UI exposes a review queue (`triager` or `admin` role) for confirmation.

```sql
CREATE TABLE entity_aliases (
    canonical_name  TEXT NOT NULL,
    alias           TEXT NOT NULL,
    source          TEXT NOT NULL CHECK (source IN ('manual','llm','catalog')),
    confidence      NUMERIC(3,2) NOT NULL DEFAULT 1.0,
    confirmed_at    TIMESTAMPTZ,
    PRIMARY KEY (canonical_name, alias)
);

CREATE TABLE entity_alias_proposals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID REFERENCES tenants(id),  -- nullable for global aliases
    raw_entity          TEXT NOT NULL,
    proposed_canonical  TEXT NOT NULL,
    confidence          NUMERIC(3,2) NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('pending','accepted','rejected')),
    reviewed_by         UUID REFERENCES users(id),
    reviewed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 6.2 Cost guardrails

- Stage A runs on every event, in-process, ~µs per entity.
- Stage B runs hourly, capped at 500 entities/hour. Excess defers to next batch.
- LLM call uses Carver's existing Anthropic API account (no Pred-Oracle-specific provisioning).

---

## 7. Filter Engine

The filter engine is the heart of the spine. Every module consumes its output.

### 7.1 Filter expression AST

Filters are JSON documents. Stored in `saved_filters.filter_expr` JSONB. Example:

```json
{
  "and": [
    {"in": {"field": "update_type", "values": ["enforcement", "final rule", "proposed rule"]}},
    {"intersects": {"field": "impacted_business_types", "values": ["Event Contracts", "Sports Betting", "Derivatives Exchanges"]}},
    {"gte": {"field": "urgency_score", "value": 7}},
    {
      "or": [
        {"intersects": {"field": "entities", "catalog": "tenant_entities"}},
        {"contains": {"field": "title", "value": "prediction market", "case_insensitive": true}}
      ]
    }
  ]
}
```

### 7.2 Supported operators

| Operator | Shape | Applies to fields |
|---|---|---|
| `and`, `or` | `{"and": [<expr>, ...]}` | (logical) |
| `not` | `{"not": <expr>}` | (logical) |
| `eq`, `ne` | `{"eq": {"field": "<f>", "value": <v>}}` | scalar |
| `gt`, `gte`, `lt`, `lte` | `{"gte": {"field": "<f>", "value": <v>}}` | numeric, date |
| `in`, `not_in` | `{"in": {"field": "<f>", "values": [<v>, ...]}}` | scalar |
| `intersects` | `{"intersects": {"field": "<f>", "values": [...]}}` or `{"intersects": {"field": "<f>", "catalog": "tenant_entities"}}` | array fields |
| `contains` | `{"contains": {"field": "<f>", "value": "<substr>", "case_insensitive": true}}` | text |
| `before`, `after` | `{"after": {"field": "<f>", "value": "2026-01-01"}}` or `{"after": {"field": "<f>", "relative": "-30d"}}` | date |
| `within_days` | `{"within_days": {"field": "<f>", "days": 14, "anchor": "now"}}` | date |

Allowed `field` values are restricted to the projected columns on `regulatory_events` (§ 4.1) — no arbitrary JSONB paths in V1 (avoids accidental SQL-injection vectors and unindexed scans).

Allowed `catalog` values: `tenant_entities` (resolves to `entity_catalog_entries.canonical_name` for the current tenant), `tenant_jurisdictions` (operating + considering statuses), `tenant_settlement_entities` (union of `settlement_entities` across active listed contracts).

### 7.3 Compilation paths

Two compilation targets:

1. **SQL compiler** (`filter_engine.compile_sql(expr) -> (sql_where: str, params: dict)`) — for batch evaluation, dashboards, exports. Compiles AST to a parameterized PostgreSQL WHERE clause against `regulatory_events`, using `WITH tenant_catalogs AS (...)` CTE to materialize tenant catalogs.
2. **In-memory compiler** (`filter_engine.compile_predicate(expr) -> Callable[[Event], bool]`) — for per-event streaming evaluation against an already-loaded `Event` model. Used by the post-ingestion fan-out path.

Both compilers must agree (property test: random AST + random event → same verdict from both).

### 7.4 Per-event fan-out

After ingestion, the `evaluate_filters(event_id)` ARQ job:

1. Loads the event from `regulatory_events`.
2. For each tenant: loads tenant's enabled `saved_filters` (where `is_alert_source = TRUE` OR referenced by a module's live view).
3. For each filter: evaluates the predicate against the event (in-memory compiler).
4. On match: INSERT into `filter_matches` (idempotent on `(tenant_id, event_id, saved_filter_id)`).
5. For each new `filter_matches` row where the filter is an alert source: enqueue `dispatch_notifications(filter_match_id)`.

```sql
CREATE TABLE saved_filters (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id),
    created_by              UUID NOT NULL REFERENCES users(id),
    name                    TEXT NOT NULL,
    filter_expr             JSONB NOT NULL,
    description             TEXT,
    is_alert_source         BOOLEAN NOT NULL DEFAULT FALSE,
    alert_channels          JSONB,        -- {"slack":["#compliance"],"email":["gc@x.com"],"sms":["+1..."]}
    alert_min_urgency       INT,          -- only fire above threshold
    alert_min_impact        INT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE filter_matches (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id),
    event_id                UUID NOT NULL REFERENCES regulatory_events(id),
    saved_filter_id         UUID NOT NULL REFERENCES saved_filters(id),
    matched_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, event_id, saved_filter_id)
);

CREATE INDEX filter_matches_tenant_event_idx ON filter_matches(tenant_id, event_id);
CREATE INDEX filter_matches_saved_filter_idx ON filter_matches(saved_filter_id);
ALTER TABLE saved_filters    ENABLE ROW LEVEL SECURITY;
ALTER TABLE filter_matches   ENABLE ROW LEVEL SECURITY;
CREATE POLICY saved_filters_tenant_isolation  ON saved_filters
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
CREATE POLICY filter_matches_tenant_isolation ON filter_matches
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

### 7.5 Filter editor UI (in the operator app)

- Visual builder (HTMX-driven nested groups) AND raw JSON edit pane (advanced users).
- Live preview: "Show last 30 days of events matching this filter" — runs SQL compiler against `regulatory_events` with a `LIMIT 50`.
- Saved-filter management: list, edit, clone, delete, toggle-as-alert-source.

---

## 8. Notification Dispatcher

### 8.1 Channels and per-tenant configuration

Per-tenant integration credentials live in `tenant_integrations`:

```sql
CREATE TABLE tenant_integrations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    channel         TEXT NOT NULL CHECK (channel IN ('slack','email','sms','webhook')),
    config          JSONB NOT NULL,   -- channel-specific; never logged or returned via GET
    secret_ref      TEXT,             -- pointer to Secrets Manager key for credentials
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, channel)
);

ALTER TABLE tenant_integrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_integrations_isolation ON tenant_integrations
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

Config examples:
- Slack: `{"workspace": "...", "default_channel": "#compliance", "channel_overrides": {"urgency:8+": "#oncall"}}`. Token lives in Secrets Manager keyed by `secret_ref`.
- Email: `{"default_recipients": ["gc@x.com"], "from_address": "alerts@predoracle.example"}`. Postmark token by `secret_ref`.
- SMS: `{"pager_users": ["+1..."]}`. Twilio creds by `secret_ref`.
- Webhook: `{"endpoint": "https://customer.example/grc/webhook", "version": "v1"}`. HMAC secret by `secret_ref`.

### 8.2 Dispatcher logic

`dispatch_notifications(filter_match_id)` ARQ job:

1. Load `filter_match` + `saved_filter` + event + tenant integrations.
2. For each channel in `saved_filter.alert_channels`:
   - Render a channel-specific message (Slack Block Kit / HTML email / SMS short form / webhook JSON).
   - Check per-tenant rate-limit (Redis token bucket; defaults in § 9.3).
   - Send via channel client; record `notification_dispatches` row.
3. On per-channel failure, retry up to 3 times with exponential backoff (1s, 5s, 30s). After exhaustion, write `failed` status and surface in tenant admin dashboard.

```sql
CREATE TABLE notification_dispatches (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    filter_match_id     UUID NOT NULL REFERENCES filter_matches(id),
    channel             TEXT NOT NULL,
    target              TEXT NOT NULL,                    -- channel/email/phone/webhook URL
    status              TEXT NOT NULL CHECK (status IN ('pending','sent','failed','suppressed')),
    attempts            INT NOT NULL DEFAULT 0,
    last_error          TEXT,
    sent_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE notification_dispatches ENABLE ROW LEVEL SECURITY;
CREATE POLICY notification_dispatches_isolation ON notification_dispatches
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

### 8.3 Message templates

Lives in `app/notifications/templates/`. One Jinja template per (channel, message_kind). Example kinds:

- `alpha.alert.slack.j2` — Slack Block Kit for α regulatory-risk alert.
- `alpha.alert.email.j2` — email for same.
- `gamma.contract_touched.slack.j2` — γ contract-watch alert.
- `gamma.contract_touched.email.j2`
- `beta.weekly_digest.email.j2`

Templates have access to: `event`, `filter_match`, `saved_filter`, `tenant`, `module_context`.

---

## 9. Outbound Webhook Delivery

### 9.1 Persistence

```sql
CREATE TABLE webhook_deliveries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    endpoint            TEXT NOT NULL,
    payload             JSONB NOT NULL,
    signature           TEXT NOT NULL,            -- HMAC of payload with per-tenant webhook secret
    status              TEXT NOT NULL CHECK (status IN ('pending','delivered','failed','dead_lettered')),
    attempts            INT NOT NULL DEFAULT 0,
    last_attempt_at     TIMESTAMPTZ,
    next_attempt_at     TIMESTAMPTZ,
    last_response_status INT,
    last_response_body  TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX webhook_deliveries_next_attempt_idx ON webhook_deliveries(next_attempt_at)
    WHERE status = 'pending';
ALTER TABLE webhook_deliveries ENABLE ROW LEVEL SECURITY;
CREATE POLICY webhook_deliveries_isolation ON webhook_deliveries
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

### 9.2 Delivery loop

ARQ job `deliver_webhook(delivery_id)`:

1. Load `webhook_deliveries` row.
2. POST `payload` to `endpoint` with `X-PredOracle-Signature: <signature>` header, 10s timeout.
3. On 2xx: status `delivered`. Done.
4. On 4xx (non-401/429): status `failed` immediately (caller misconfiguration; retrying won't help). Notify tenant admin via email.
5. On 401/429/5xx/timeout: increment `attempts`, schedule next attempt per backoff: 1s, 5s, 30s, 5m, 1h, 6h, 24h. After 7 attempts (`attempts >= 7`): status `dead_lettered`. Notify tenant admin.

Separate ARQ scheduler picks up `status='pending' AND next_attempt_at <= now()` every 10s.

### 9.3 Rate limits

Per-tenant default: 1000 calls/hour soft (warn), 10000/hour hard (defer to next hour). Redis token-bucket keyed `webhook_rl:{tenant_id}:{hour_bucket}`.

---

## 10. Audit Log

```sql
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID REFERENCES tenants(id),   -- nullable for global staff ops
    actor_user_id   UUID REFERENCES users(id),
    actor_kind      TEXT NOT NULL CHECK (actor_kind IN ('user','system','staff_impersonation')),
    action          TEXT NOT NULL,                 -- e.g., 'ticket.status_changed', 'catalog.entity_added'
    target_kind     TEXT NOT NULL,                 -- e.g., 'ticket', 'entity_catalog_entry'
    target_id       TEXT,
    payload         JSONB,                         -- before/after diff, request body, etc.
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX audit_log_tenant_created_idx ON audit_log(tenant_id, created_at DESC);
CREATE INDEX audit_log_actor_idx          ON audit_log(actor_user_id, created_at DESC);
CREATE INDEX audit_log_action_idx         ON audit_log(action, created_at DESC);
```

**What writes to audit_log:**
- Every state-changing API endpoint (decorator-applied).
- Every tenant catalog mutation (entity, listed-contract, jurisdictional-footprint).
- Every saved-filter mutation.
- Every ticket transition (α).
- Every staff impersonation start/end.
- Every integration-credential mutation (config diff only, never secret values).

Audit-log retention: 7 years (regulator-compliance default). Storage cost is negligible; revisit if it isn't.

---

## 11. Admin APIs

Authenticated, JSON, behind `/api/v1`. All require a tenant context except staff-only routes under `/api/staff`.

| Endpoint | Method | Role | Purpose |
|---|---|---|---|
| `/api/v1/me` | GET | any | Current user + tenant. |
| `/api/v1/users` | GET, POST | admin | List + invite users. |
| `/api/v1/users/{id}` | PATCH, DELETE | admin | Update role / disable. |
| `/api/v1/catalog/entities` | GET, POST | admin (POST), any (GET) | CRUD entity catalog. |
| `/api/v1/catalog/entities/upload` | POST (multipart) | admin | CSV bulk-upload. |
| `/api/v1/catalog/contracts` | GET, POST | admin (POST), any (GET) | CRUD listed contracts. |
| `/api/v1/catalog/contracts/upload` | POST (multipart) | admin | CSV bulk-upload. |
| `/api/v1/catalog/jurisdictions` | GET, POST | admin (POST), any (GET) | CRUD jurisdictional footprint. |
| `/api/v1/filters` | GET, POST | any (GET), triager+ (POST) | CRUD saved filters. |
| `/api/v1/filters/{id}` | GET, PATCH, DELETE | triager+ for mutation | |
| `/api/v1/filters/preview` | POST | triager+ | Test a filter expression against last 30 days. |
| `/api/v1/events/{id}` | GET | any | Read one event (raw + projected). |
| `/api/v1/integrations` | GET, PATCH | admin | Manage integration configs (never returns secrets). |
| `/api/v1/audit-log` | GET | admin | Tenant's audit log with filters. |
| `/api/staff/tenants` | GET, POST | staff | Provision new tenants. |
| `/api/staff/impersonate/{tenant_id}` | POST | staff | Start impersonation session. |
| `/internal/ingest/carver` | POST | HMAC | Carver ingestion (§ 3). |

OpenAPI spec auto-generated from FastAPI routes and published at `/api/v1/openapi.json`.

---

## 12. Acceptance Criteria

The spine is "done enough to start α" when:

- [ ] Tenant + user + role + auth (SSO and local) all work end-to-end; an admin can invite a triager, and the triager can log in via OIDC.
- [ ] Carver ingestion endpoint accepts a sample payload, persists `regulatory_events`, idempotency on duplicate `carver_id` confirmed by integration test.
- [ ] All projected columns are populated from a real Carver entry sample; date parsing handles Hijri.
- [ ] `entity_catalog_entries`, `listed_contracts`, `jurisdictional_footprint` ingest from CSV.
- [ ] Filter engine: SQL and in-memory compilers agree on a property test (1000 random ASTs × 100 random events).
- [ ] `saved_filters` + `filter_matches` end-to-end: create a filter, ingest a matching event, see a `filter_matches` row.
- [ ] Slack and email notification dispatched on a filter match; `notification_dispatches` row recorded.
- [ ] Outbound webhook delivered with HMAC signature; retry path exercised by integration test.
- [ ] Audit log written for: ticket transition (will use α's, fake it with a stub), catalog mutation, integration mutation, staff impersonation.
- [ ] RLS policies prevent cross-tenant data leakage (negative integration test).
- [ ] Pred-Oracle visibility latency (Carver POST → `filter_matches` row) measured in CI: <60s at p95 with 100 events queued.

---

## 13. Open Questions (spine-local)

| # | Question | Suggested resolution |
|---|---|---|
| S1 | Are there `update_type` values in Carver's enum we don't support in filter UI dropdowns? | Generate enum from a sampled month of production Carver data; bake into filter UI as a SELECT options list with "other (regex)" escape hatch. Resolve at M2. |
| S2 | What's the throughput envelope we should design ingestion for? | Strategy doc implies "hundreds/day" today; design for 10k/day burst to leave headroom. Confirm with Carver data team. |
| S3 | Should `regulatory_events` be partitioned by month from day 1? | Not in V1 (<1M rows expected by M12). Add partition migration in V2 when row counts justify. |
| S4 | How are platform-customer entity catalogs initially seeded? | Pred-Oracle CS imports a starter catalog per design partner (the platform itself, exec staff names, known competitors, parent/subsidiaries). Customer extends via UI. |
| S5 | Cross-tenant filter sharing — needed in V1? | No. Each tenant's filters are tenant-scoped. Pred-Oracle staff can publish "starter pack" filters as a SQL seed for new tenants. |
