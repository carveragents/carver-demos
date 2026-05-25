# Future-State Production Specs

These are V1 production-grade implementation specs derived from [`../../product-strategy.md`](../../product-strategy.md). They describe a full multi-tenant SaaS build of Pred-Oracle — what we would build for paying customers, not what we are building right now.

> **This is not the active spec set.** The active deliverable is a **static-site demo** against real Carver data. See [`../`](../) for the demo specs.

---

## Why these are deferred

After the production specs were drafted, the build scope was narrowed (2026-05-19) to a **demo first** — a static site that walks a prospect through the three V1 use cases (α / γ / β) using real Carver annotations and hand-curated platform context. The full-SaaS architecture in these documents (multi-tenancy, RLS, ARQ queues, ingestion APIs, OIDC SSO, notification dispatcher, audit-log retention) is overbuilt for that goal.

These documents stay here because:
- They are the right design *if and when* Pred-Oracle becomes a real product. Don't re-derive from scratch later.
- The data-model decisions (Carver field projection, filter-engine AST, entity-resolution two-stage approach, cascade-rule schema) translate forward unchanged.
- The open-questions register in `00-v1-overview.md` § 6 names the gating decisions that still apply at production-build time.

---

## What's in this directory

| File | Purpose |
|---|---|
| [`00-v1-overview.md`](00-v1-overview.md) | V1 scope, sequencing, recommended tech stack with rationale, open-questions register. |
| [`10-data-spine.md`](10-data-spine.md) | Tenancy + RBAC, Carver ingestion, event store, customer catalogs, entity resolution, filter engine, notification dispatcher, audit log. |
| [`20-alpha-regulatory-risk-radar.md`](20-alpha-regulatory-risk-radar.md) | α module: triage queue, alerts, per-jurisdiction dashboard, audit-log export. |
| [`30-gamma-listed-asset-risk.md`](30-gamma-listed-asset-risk.md) | γ module: pre-listing scan, contract-watch, regulatory-heat scoring. |
| [`40-beta-strategic-expansion.md`](40-beta-strategic-expansion.md) | β module: heat-map, cascade rules, quarterly report generator. |

Last reviewed: 2026-05-19 (initial draft).

---

## Promotion criteria

These specs are eligible to become the active set when **all** of the following are true:

- ≥1 paying design partner has signed beyond the demo (commercial validation).
- Carver data team has confirmed regulator coverage adequate for V1 buyer use cases (open question Q1).
- A funded engineering team is allocated to a multi-month build.
- The demo has surfaced concrete shape-changes to the production spec — those edits get folded in before promotion.

Until then: **do not implement from these documents**. Implement from `../`.
