# V1 Implementation Overview

> **Status:** Draft, pending team review.
> **Derived from:** [`../product-strategy.md`](../product-strategy.md) (the canonical strategy doc).
> **Audience:** Pred-Oracle product/engineering team.

This document is the entry point for V1 implementation specs. Read it first, then drill into the module specs.

---

## 1. V1 Scope (restated)

Three product modules sitting on one shared data spine. Quoted timelines from strategy doc § 6.2:

| Module | Buyer | First ship | Strategy doc ref |
|---|---|---|---|
| **α — Regulatory Risk Radar** | GC / CCO | Month 6 | § 4.1, spec [`20-alpha-regulatory-risk-radar.md`](20-alpha-regulatory-risk-radar.md) |
| **γ — Listed-Asset Regulatory Risk** | Head of Listing / Trading Risk | Month 9 | § 4.2, spec [`30-gamma-listed-asset-risk.md`](30-gamma-listed-asset-risk.md) |
| **β — Strategic Expansion Intelligence** | Head of International / Corp Dev | Month 12 | § 4.3, spec [`40-beta-strategic-expansion.md`](40-beta-strategic-expansion.md) |
| **Shared data spine** | (foundation) | Months 0–6 | § 5, spec [`10-data-spine.md`](10-data-spine.md) |

**Out of V1:** δ (Policy & Lobbying), ε (Audit Workbench), HFT-grade real-time, embedded SDK. See strategy § 6.1.

---

## 2. Build Sequencing & Critical Path

```
Month 0          3              6              9              12
|----------------|--------------|--------------|--------------|
[ data spine                   ]
[ α MVP (internal proxy users) ]
                [ α GA + 2 design partners        ]
                          [ γ build              ][ γ live ]
                                    [ β build               ][ β live ]
```

**Dependencies between specs:**

- **`10-data-spine`** is a hard prerequisite for all three modules. Specifically: event store, Carver ingestion, filter engine, tenancy, RBAC, alerting infrastructure, and customer-catalog ingestion.
- **`20-alpha`** depends on the spine, customer-catalog (entity), and alerting/triage subsystems.
- **`30-gamma`** depends on the spine, customer-catalog (listed-contract), entity resolution, and `20-alpha`'s alerting infrastructure.
- **`40-beta`** depends on the spine, customer-catalog (jurisdictional-footprint), and at least 6 months of accrued event-store history for the predictive-cascade layer to have priors. It reuses the spine's filter engine for heat-map aggregations.

**Concurrency note:** Months 4–6 are the highest-leverage period — α is being polished to GA while γ work begins on the same spine. Plan for a small parallel-development pod by month 4.

---

## 3. Recommended Tech Stack

These are recommendations with rationale. Lock-in happens at engineering kickoff; flag pushback on any item before code starts.

### 3.1 Runtime & language

- **Python 3.10** — already pinned by repo (see [`../development.md`](../development.md)). All modules are Python.

### 3.2 Web framework & UI

- **FastAPI** for HTTP API (async, OpenAPI-first, mature for REST + server-rendered hybrid).
- **Server-rendered HTML** via Jinja2 + HTMX + Alpine.js + Tailwind CSS for the operator UI. Rationale: legal/compliance users do triage queues and dashboards — fast page loads, accessibility, audit trail, and low frontend complexity beat SPA polish. β heat-maps and the contract-watch board use **Apache ECharts** rendered client-side with server-supplied JSON.
- **Uvicorn** ASGI server in dev; **Gunicorn + Uvicorn workers** in prod.

### 3.3 Data layer

- **PostgreSQL 16** — primary datastore. JSONB columns for raw Carver payloads; relational tables for derived/enriched data and tenancy. Native Row-Level Security (RLS) for tenant isolation.
- **SQLAlchemy 2.0** (async API) + **Alembic** for migrations.
- **`pg_trgm`** extension for fuzzy entity-name matching.
- **Redis 7** for caching, ARQ queue broker, and short-lived per-request state (rate-limit counters).

### 3.4 Background work

- **ARQ** (async Redis queue) for: Carver-feed polling, per-event filter fan-out, alert dispatch, scheduled report generation, listed-contract refresh.
- Rationale over Celery: lighter, async-native, fewer moving parts. Workload is bursty but bounded — same-day cadence, not HFT.

### 3.5 Auth & multi-tenancy

- **Authlib** for OAuth2/OIDC. Each customer brings their IdP (Okta / Auth0 / Google Workspace / Microsoft Entra) for SSO; a local-username/password fallback exists for design-partner bootstrap.
- **Multi-tenancy model:**
  - One **tenant** per platform customer (e.g., Kalshi, Polymarket).
  - All app-domain tables carry a `tenant_id` foreign key.
  - PostgreSQL **RLS policies** enforce tenant isolation at the DB layer (defense in depth beyond app-layer `WHERE` clauses).
  - Per-request middleware issues `SET LOCAL app.current_tenant = '<uuid>'` from the authenticated session.
  - Carver-side ingestion is *global* (no tenant scoping on raw events); per-tenant matching happens at filter-evaluation time.

### 3.6 RBAC (per-tenant)

Three V1 roles per tenant:
- **`admin`** — manages tenant catalogs, users, integration credentials.
- **`triager`** — operates the triage queue, sees alerts, transitions ticket status. GC / CCO / counsel.
- **`viewer`** — read-only access to dashboards and tickets. Board / exec / auditor.

Cross-tenant **`pred_oracle_staff`** role for the Pred-Oracle ops team — explicit per-tenant impersonation, full audit-logged.

### 3.7 Notification channels

- **Slack** via per-tenant incoming-webhook URL + `slack_sdk` for richer Block Kit messages.
- **Email** via **Postmark** (transactional). Jinja-templated HTML + plaintext.
- **SMS** via **Twilio** for urgency-8+ pages (configurable per user).
- **Outbound webhooks** for customer GRC/Jira integrations via `httpx` with exponential backoff + dead-letter queue.

### 3.8 PDF / report generation

- **WeasyPrint** for HTML → PDF (used by β quarterly reports and α audit-log exports). Python-native, no Chrome dependency.

### 3.9 Tooling

- **uv** for dependency resolution and virtualenv management.
- **ruff** for lint + format.
- **mypy** strict mode for type-checking.
- **pytest** + `pytest-asyncio` + **testcontainers** (Postgres + Redis) + `factory_boy` + `hypothesis`.
- **GitHub Actions** for CI: lint → typecheck → test → build → push container.
- **Docker** images; deployment target TBD (Fly.io / Render / AWS ECS) — chosen at infra-readiness milestone in Month 3.

### 3.10 Observability

- **structlog** for structured JSON logs.
- **OpenTelemetry** SDK for traces + metrics. Exporter target chosen with deployment target.
- **Sentry** for error tracking from Month 3 onward (free tier sufficient through design-partner phase).

### 3.11 Secrets

- Dev: `.env` files (gitignored), `python-dotenv` loader.
- Prod: **AWS Secrets Manager** (or Doppler if deploying outside AWS). No secret values in container images or git.

---

## 4. Multi-Tenancy Data-Model Convention

Every app-domain table (not raw Carver mirror tables) MUST follow this pattern. Specs below assume it.

```sql
-- Pattern for all tenant-scoped tables
CREATE TABLE example (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    -- ... domain columns ...
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX example_tenant_id_idx ON example(tenant_id);

ALTER TABLE example ENABLE ROW LEVEL SECURITY;
CREATE POLICY example_tenant_isolation ON example
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

Per-request middleware sets the session variable; SQLAlchemy connection-pool checkout hook applies it. See [`10-data-spine.md`](10-data-spine.md) § "Tenancy".

---

## 5. Success Criteria

From strategy doc § 10, made testable here.

### 5.1 V1 milestones (gating)

| Milestone | Definition of done |
|---|---|
| **M3: α internal MVP** | α deployed to staging; ≥1 Carver feed ingested into event store; ≥10 manually-triaged tickets through full lifecycle; alert sent to internal Slack. |
| **M6: α GA** | 2 design partners onboarded with their entity catalog; ≥1 production alert per partner per week; audit-log export verified. |
| **M9: γ live** | Both design partners have ≥1 listed-contract catalog imported; ≥1 pre-listing scan run per week per partner; contract-watch dashboard shows live regulatory-heat scores. |
| **M12: β live** | Both design partners have jurisdictional-footprint catalogs; quarterly heat-map dashboard live; at least one quarterly report auto-drafted and accepted by the partner. |

### 5.2 North-star metric

- **Triaged-update throughput per customer per week** (strategy § 10.2) — instrumented from the first ticket transition.

### 5.3 Leading indicators (months 0–6)

| Metric | Target |
|---|---|
| Carver-coverage completeness (% of target regulators ingested) | ≥80% by M6 |
| Pred-Oracle visibility latency (publication → triage-queue) | <12h median, <24h p95 |
| Alert relevance (% rated actionable by GC) | >70% |
| Triage time (alert fired → status out of "new", urgency ≥8) | <2h median |

### 5.4 Lagging indicators (months 6–12)

| Metric | Target |
|---|---|
| Design-partner logo retention | 100% into year 2 |
| Net revenue retention | ≥120% |
| Follow-on sales cycle length | <6 months by M12 |

---

## 6. Open Questions Register

From strategy § 6.4, with proposed answers. Items marked "DECIDE BY" gate downstream work.

| # | Question | Proposed answer | Owner | Decide by |
|---|---|---|---|---|
| Q1 | Which prediction-market-relevant regulators are *not* in Carver coverage? | Run coverage audit against a target list assembled in M1 (state gambling commissions, tribal authorities, ANJ/KSA/GRA/UKGC/etc., FATF/IOSCO/BCBS). Gaps go on a coordinated Carver-data fill backlog. | Pred-Oracle PM + Carver data lead | M2 |
| Q2 | Do Kalshi / Polymarket expose public listed-contract APIs? | **Kalshi: yes** (public market-list API, polled hourly). **Polymarket: yes** (public CLOB API, polled hourly). Where APIs absent or rate-limited, fall back to per-tenant CSV upload + manual periodic refresh. Plan for both code paths. | γ tech lead | M5 |
| Q3 | Entity catalog normalization (cross-document entity resolution) — build, buy, or use Carver's? | Build in Pred-Oracle. Deterministic exact + alias matching first (fast path); LLM-assisted fuzzy matching for ambiguous cases, with human-in-the-loop confirmation queue. See [`10-data-spine.md`](10-data-spine.md) § "Entity resolution". | Spine tech lead | M2 |
| Q4 | Multi-tenant auth / RBAC — inherit Carver's or build standalone? | Standalone in V1 (Authlib OAuth2/OIDC per-tenant IdP). Re-evaluate at M6 once a Carver SSO posture is clearer. | Spine tech lead | M1 |
| Q5 | Outbound webhook rate-limit / SLA model? | Per-tenant quota: 1000 calls/hour soft, 10000/hour hard. SLA: 99.5% delivery within 60s; retry with exponential backoff (1s, 5s, 30s, 5m, 1h); dead-letter after 24h with admin notification. | Spine tech lead | M3 |
| Q6 | PDF generation for β quarterly report — build or buy? | Build: WeasyPrint (HTML→PDF) sufficient for V1. Revisit at M12 if multi-page typesetting becomes painful. | β tech lead | M9 |
| Q7 | Re-run annotation on Carver archival content to extend history? | Out of V1 scope. Coordinate with Carver data team as a separate workstream; β's predictive-cascade layer will be rule-based in V1 and learned-pattern in V2+ regardless. | Pred-Oracle PM + Carver data lead | (out of V1) |

---

## 7. How to Read the Per-Module Specs

Each module spec follows the same skeleton:

1. **Purpose & buyer** — 1-paragraph restatement.
2. **In scope / out of scope** — boundaries.
3. **Data model** — tables, columns, indexes (SQL-shaped).
4. **APIs** — REST endpoints with method, path, auth requirement, request/response shapes.
5. **UI surfaces** — screens and their key components, with the data they bind to.
6. **Background jobs** — what runs on a schedule and what triggers on an event.
7. **Integrations** — Slack/email/SMS/webhook touch-points.
8. **Acceptance criteria** — testable statements that gate the module's milestone.
9. **Open questions** — module-local issues to resolve before code.

Start with the data-spine spec — every module assumes its primitives.
