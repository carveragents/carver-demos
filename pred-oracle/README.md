# Pred-Oracle

A vertical compliance-intelligence platform for prediction-market operators (Kalshi, Polymarket, and the broader CFTC-licensed DCM / event-contract category), built on top of Carver's existing regulatory-annotation pipeline.

**Project status:** Stage 0 implemented — static demo site builds locally and is ready for GitHub Pages deploy.

## What this project is

Pred-Oracle re-aims Carver's `entry_annotation` workflow output at a new buyer: the General Counsel / Chief Compliance Officer / Head of International / Listing-Risk teams *inside* prediction-market operators. Instead of selling annotated regulatory data to platforms so they can build user-facing products with it (data-vendor play), Pred-Oracle is consumed by the platforms' own staff to defend the business from enforcement risk, plan jurisdictional expansion, and monitor regulatory exposure on listed contracts.

## Quick start

```bash
uv sync --extra dev
make build       # produces site/
make serve       # local preview at localhost:8000
```

See `docs/development.md` for full setup details.

## Where to start

1. **`docs/product-strategy.md`** — the canonical strategy and product overview. Read this first. Self-contained: covers market context, the five product modules, V1 scope, sequencing, pricing, and the data spine.
2. **Carver data source** — the regulatory annotations Pred-Oracle consumes are produced by the `entry_annotation` workflow in the sibling repo at `../carver-dags/workflows/entry_annotation/`. See `docs/product-strategy.md` § "Appendix A: Carver Data Model Reference" for the field schema.

## V1 scope

Three bundled modules:
- **α — Regulatory Risk Radar** (the platform's own enforcement exposure)
- **γ — Listed-Asset Regulatory Risk** (regulatory events touching listed contracts)
- **β — Strategic Expansion Intelligence** (jurisdiction × update_type heat-maps)

Built on a shared event-store data spine. Staged delivery: α → γ → β.

## Roadmap

- **δ — Policy & Lobbying Intelligence**
- **ε — Regulatory Audit Workbench**

Both deferred to V2+. Rationale in `docs/product-strategy.md` § 4 and § 7.

## How this folder is organized

```
pred-oracle/
├── README.md                    # This file
├── CLAUDE.md                    # Agent guidance
├── Makefile                     # make pull / slice / build / serve / test / lint / clean
├── pyproject.toml               # uv-managed deps (Python 3.10)
├── .github/workflows/           # CI: lint + test + GH Pages deploy
├── build/                       # Python build pipeline + Jinja templates + static assets
├── data/                        # Real Carver pull, hand-curated platform YAMLs
├── tests/                       # pytest suite (37 tests)
└── docs/
    ├── README.md                # Docs index
    ├── product-strategy.md      # Canonical strategy
    ├── specs/                   # Active demo specs (00 scope → 50 β walkthrough)
    ├── specs/future/            # Production-grade V1 specs, deferred
    ├── superpowers/plans/       # Implementation plans (Stage 0 done)
    ├── development.md           # Dev environment setup
    └── LESSONS.md               # Running session notes
```

## Stage 1 — α walkthrough

The α scene (Sara Chen / GC) renders at `/alpha/`:

- `/alpha/` — regulatory triage inbox (15 rows, curated wow ticket at top)
- `/alpha/tickets/{id}/` — 5 pre-rendered ticket-detail pages
- `/alpha/dashboard/` — US-states choropleth (90-day window, ECharts)
- `/alpha/audit-export/` — synthetic transition log + sample PDF

### Building locally

```bash
uv run python build/pull_artifacts.py    # only if data/_scratch/artifacts.jsonl is missing
uv run python build/generate_slices.py
uv run python build/generate.py
make serve   # http://localhost:8000/
```

### Curation

The wow ticket and 4 supporting ticket-detail picks live in `data/alpha-curation.yml`. Edit those `feed_entry_id`s to swap picks; re-run `generate_slices.py` to regenerate.

Filter rules live in `build/_scoring.py` (`is_inbox_eligible`, `wow_score`). Dashboard window is also in `alpha-curation.yml`.

### Specs

- `docs/specs/30-alpha-walkthrough.md` — α-scene narrative spec
- `docs/specs/STAGE_1_NOTES.md` — load-bearing schema reference
- `docs/specs/STAGE_1_DONE.md` — acceptance log for this stage

## Stage 2 — γ walkthrough

The γ scene ("Marcus Vega, Head of Listing") renders at `/gamma/`:

- `/gamma/` — Marcus's three-card overview
- `/gamma/scan/` — 3-tab pre-listing scan (TikTok ban, Solana ETF 2027, state action against Kalshi)
- `/gamma/dashboard/` — contract-watch board with heat + sparklines (5 active contracts)
- `/gamma/contracts/{id}/` — 5 pre-rendered contract details (2 active + 3 retrospectives)

### Refreshing contract metadata

```bash
uv run python build/pull_kalshi_curated.py --mode=fresh
uv run python build/pull_polymarket_curated.py --mode=fresh
```

Non-destructive: if upstream returns 404, the cached metadata is kept and `stale: true` is recorded.

### Curation

- `data/gamma-curation.yml` — picks + `build_date` + synthetic listing-risk tickets.
- `data/platforms/{kalshi,polymarket}/contracts.yml` — pick-list + cached upstream metadata + hand-curated `settlement_entities` (live APIs don't return regulators/corporations named in resolution criteria).
- `data/platforms/{kalshi,polymarket}/contracts/{id}.yml` — hand-curated retrospective contracts (Wayback-/news-sourced).

### Specs

- `docs/specs/40-gamma-walkthrough.md` — γ narrative spec (Task 5 reframed §2.4 wow from price-overlay to signal-precedence math).
- `docs/specs/STAGE_2_NOTES.md` — Stage 2 acceptance log + schema notes + lessons learned.

## Stage 3 — β walkthrough

The β scene ("Priya Kapur, Head of International") renders at `/beta/`:

- `/beta/` — Priya's three-card overview (heat-map · cascades · quarterly report).
- `/beta/heatmap/` — world choropleth + US-states inset + France retrospective with 18-month pressure chart and 5 annotation callouts.
- `/beta/cascades/` — 3 cascade cards (FATF, BCBS, ESMA) with member jurisdictions tagged by footprint role.
- `/beta/report/` — Q2 2026 quarterly intelligence report: headline stats, pressure-rising / -easing, watch list (Brazil + Singapore + Australia), γ touchpoints, downloadable PDF.

### Curation

- `data/beta-curation.yml` — `build_date`, retrospective focus, featured cascade ids, watch-list picks, report window.
- `data/platforms/{kalshi,polymarket}/footprint.yml` — operating / considering / closed jurisdictions per platform.
- `data/cascades.yml` — hand-curated cascade rules (trigger URL, members, follow window, historical hit-rate).
- `data/sources/watch-list-evidence.md` — public-record evidence per watch-list jurisdiction.

### Specs

- `docs/specs/50-beta-walkthrough.md` — β narrative spec (Task 4 reframed §2.2 wow from ANJ to AMF/ESMA pressure).
- `docs/specs/STAGE_3_NOTES.md` — Stage 3 acceptance log + schema notes + lessons learned.

## Audience

- **Carver leadership** — read `docs/product-strategy.md` § 1, 2, 8, 9 for buy-in.
- **Product/engg team** — read `docs/product-strategy.md` § 3, 4, 5, 6 to begin spec/implementation.
