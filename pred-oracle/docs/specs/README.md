# Pred-Oracle Demo Specs

This directory specifies the **Pred-Oracle demo** — a static web walkthrough that takes a prospective customer (GC, CCO, Head of Listing, or Head of International at a prediction-market platform) through three real use cases, powered by real Carver-annotated regulatory data and a small amount of hand-curated platform context.

> **Specs are scoped to a demo, not a production product.** Production-grade V1 specs are deferred to [`future/`](future/) until a paying design partner is signed and an engineering team is allocated.

---

## Reading Order

Read top to bottom. Each doc builds on the one above.

| Step | Doc | What it tells you |
|---|---|---|
| 1 | [`00-demo-scope.md`](00-demo-scope.md) | Audience, narrative arc, success criteria, what's out of scope, staging plan. |
| 2 | [`10-data-prep.md`](10-data-prep.md) | How to pull real Carver data, what synthetic platform context to fabricate, how to slice it into per-page JSON. |
| 3 | [`20-site-build.md`](20-site-build.md) | Tech stack (Python + Jinja2 + Tailwind + ECharts), repo layout, build pipeline, deploy target. |
| 4 | [`30-alpha-walkthrough.md`](30-alpha-walkthrough.md) | Stage 1: GC inbox scene. Page-by-page content + acceptance criteria. |
| 5 | [`40-gamma-walkthrough.md`](40-gamma-walkthrough.md) | Stage 2: Listing-team scene with Solana ETF retrospective. |
| 6 | [`50-beta-walkthrough.md`](50-beta-walkthrough.md) | Stage 3: International-team scene with France retrospective + quarterly report. |

---

## Build Stages

The demo is staged so each scene ships independently. Total demo runtime: ~15 minutes when complete.

```
Stage 0: data + scaffolding
   └─ pull Carver data; build site shell; deploy landing with 3 placeholder tiles.

Stage 1: α scene
   └─ adds GC inbox, ticket detail, jurisdictional dashboard, audit-export preview.

Stage 2: γ scene
   └─ adds pre-listing scan, contract-watch dashboard, Solana ETF retrospective.

Stage 3: β scene
   └─ adds world heat-map, cascade signals, Q2 quarterly report mock.

Stage 4: polish
   └─ mobile review, copy edit, design pass, sign-off dry-run.
```

Each stage is independently demoable. Carver leadership can begin showing Stage 1 as soon as it lands while Stage 2 is under construction.

---

## How the Demo Fits Together

The demo follows three personas through one continuous Monday-to-Wednesday narrative:

```
Mon 9:00 AM       Tue 10:30 AM         Wed 11:00 AM
   ▼                  ▼                    ▼
┌──────────┐    ┌──────────────┐     ┌─────────────────┐
│ Sara     │    │ Marcus       │     │ Priya           │
│ Chen,    │    │ Vega,        │     │ Kapur,          │
│ GC       │    │ Head of      │     │ Head of         │
│ (α)      │───►│ Listing      │────►│ International   │───► Close
│          │    │ (γ)          │     │ (β)             │     CTA
└──────────┘    └──────────────┘     └─────────────────┘
   Inbox →         Pre-listing →        World heat-map →
   Ticket →        Contract watch →     Cascades →
   Dashboard →     Solana ETF case      Q2 report
   Audit log
```

Personas are fictional and labelled as such. Every regulatory event surfaced is real.

---

## Source-of-Truth Rules

Strict throughout:

| Element | Source |
|---|---|
| Regulatory events | Real Carver annotations. Never fabricated. |
| Named regulators | Real, public. Source-logged. |
| Named platform executives | Real, sourced from public press / corporate "About" pages. |
| Listed contracts | Real, copied from public Kalshi / Polymarket listings. |
| Persona names (Sara / Marcus / Priya) | Fictional. Labelled "(illustrative)" on first appearance. |
| Comment threads, status transitions, assignees | Synthetic. Carry the demo-data badge wherever they appear. |
| "Pred-Oracle would have caught X N days earlier" claims | Carver-event date vs first-mainstream-news-article date. Both linked. |

If anyone copies a fact off any page and Googles it, the fact must check out. Synthetic content is always visibly marked.

---

## What's *Not* Here

- **Production SaaS specs** — see [`future/`](future/). Don't implement from there until a paying design partner exists.
- **Buyer-persona deep-dives** — reserved for `docs/personas/` (sales motion artifact, not demo build).
- **Worked contract examples for sales context** — reserved for `docs/contracts/`.
- **Code-level TDD plans** — Stage 0 plan will be written separately via `superpowers:writing-plans` once we begin actual implementation.

---

## Open Questions

Each spec has its own per-doc question list (numbered `D*`, `DP*`, `B*`, `AW*`, `GW*`, `BW*`). The highest-priority unblockers across the whole demo:

- ✅ **D1** — Carver data source: use `carver-feeds-sdk` (decided 2026-05-19).
- ✅ **D2** — Kalshi/Polymarket: one-time API pull at build time (decided 2026-05-19).
- ✅ **D3** — Deploy: GitHub Pages (decided 2026-05-19).
- ✅ **γ retrospective contracts**: TIKTOKBAN-25APR30 + KXFEDDECISION-26MAR (decided 2026-05-19).
- ⏳ **DP1** — Whether the carver-feeds-sdk surfaces Appendix-A annotation fields directly, or whether we need a Claude pass on raw entries. Resolves at Stage 0 day 1 via live SDK call.
- ⏳ **AW1 / GW1 / BW2** — Specific real events that become wow moments, particularly: the α inbox top-priority item, and the β heat-map retrospective jurisdiction(s). **Both deferred until after the Carver pull.**

Stage 0 ordering is therefore:
1. Install `carver-feeds-sdk`; resolve `CARVER_API_KEY`; sample one entry; resolve DP1.
2. Run the prediction-market-relevance filter (data-prep § 2.1); inspect the slice.
3. Hand-pick wow moments from the slice (AW1, BW2).
4. Pull Kalshi + Polymarket APIs; pull TIKTOKBAN + KXFEDDECISION price-history.
5. Then begin scaffold + landing page (Stage 0 site deliverable).
