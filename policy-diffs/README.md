# policy-diffs

POC that converts Mastercard B2B rulebook deltas into proposed updates to a synthetic
**Acme Pay** compliance policy library — and presents the result as a static,
browser-based timeline a non-technical compliance reviewer can walk through.

Built on top of the [Carver Horizon](https://carver.ai) regulatory intelligence stack.

> *Acme Pay is a fictional company used as the customer-facing scenario for this demo.
> The eight policy areas, baseline policy text, and proposed updates are all synthetic.*

## What this demonstrates

Imagine **Acme Pay**, a fictional payments-compliance company whose AI agents enforce
card-network rules on behalf of its customers. When Mastercard updates a rulebook,
Acme Pay's internal policies — the source of truth its agents reference — must be
re-checked, updated, and re-distributed to compliance staff. Today this is a manual,
slow process; missing or late updates create compliance exposure.

This POC automates that loop end-to-end:

1. **Detect** what changed in a Mastercard B2B artifact between published versions.
2. **Classify** each change by materiality (cosmetic / clarifying / substantive / breaking).
3. **Map** each material change to the affected Acme Pay policies.
4. **Propose** the resulting policy edit (`policy.md` + `rules.yaml`) as a redline.
5. **Present** the timeline of proposals as a static HTML site a compliance reviewer
   can browse without engineering vocabulary.

The demo is anchored on the **Security Rules and Procedures – Merchant Edition (SPME)**
rulebook: 6 published Wayback versions, 5 transitions, 2022-06 → 2025-05.

## Pipeline

Six stages — deterministic upstream, LLM downstream:

```
1. Fetch    →  2. Extract   →  3. Diff       →  4. Classify  →  5. Map      →  6. Propose
   [curl       [pymupdf +      [per-section    [LLM:          [LLM: which   [LLM: emit
   Wayback]    pdfplumber]     text diff]      materiality]   Acme Pay      policy.md /
                                                              policies      rules.yaml
                                                              affected]     edits]
```

Each stage caches intermediate artifacts under `artifacts/<artifact>/...`, so re-runs
skip work already done. Cosmetic changes are dropped after classification so the LLM
mapper/proposer never see them.

The Acme Pay side evolves *sequentially* across transitions: transition N's proposer
sees the policy files as transition N-1's edits left them (tracked in-memory). The
on-disk baseline in `credio-policies/policies/` stays pinned to v1; proposed updates
live inside per-change JSON records, not in the working tree.

Full pipeline spec: [`docs/superpowers/specs/2026-05-07-policy-diffs-poc-design.md`](./docs/superpowers/specs/2026-05-07-policy-diffs-poc-design.md) § 4.

## Demo presentation (three layers)

The customer-facing surface is a static HTML site at `credio-policies/dist/`, opened
from `file://`. No JavaScript framework, no build step, no server — rendered once
at the end of the pipeline from the change-record JSONs.

| Layer | Page | Audience |
|---|---|---|
| 1 | `dist/timeline.html` — vertical timeline of all 5 transitions, with materiality counts colour-coded (red=breaking, orange=substantive, yellow=clarifying) | Exec / overview, < 30s read |
| 2 | `dist/transitions/<from>_to_<to>.html` — change-cards feed for one transition; one card per non-cosmetic Mastercard section diff | Compliance reviewer scanning impact |
| 3 | `dist/changes/<change-id>.html` — three tabs: **Side-by-side** Mastercard ↔ Acme Pay redline, **Redline** (Word-style track-changes on `policy.md`), **Raw diff** (unified) | Compliance reviewer (tabs 1-2) / engineer (tab 3) |

## Setup

Requires Python 3.12 and an OpenAI API key.

```bash
uv sync
cp .env.example .env   # then edit and set OPENAI_API_KEY
set -a; source .env; set +a
```

## Run

Full Phase 1 pipeline (all 5 SPME transitions). Cold run: ~20–30 min and $5–$15 in
LLM cost; subsequent runs hit the artifact cache and are much faster.

```bash
uv run python -m pipeline.cli run-phase --artifact spme
uv run python -m pipeline.cli render-site --artifact spme
uv run python -m pipeline.cli render-pdfs
open credio-policies/dist/timeline.html
```

## Project layout

```
policy-diffs/
├── pipeline/              # Fetch · Extract · Diff · Classify · Map · Propose stages + CLI
├── prompts/               # LLM prompts (versioned, testable in isolation)
├── presentation/          # Static-site renderer (Jinja2 templates → dist/)
├── credio-policies/       # Synthetic baseline policy library + rendered dist/ site
│   ├── policies/          #   v1 baseline policies (policy.md + rules.yaml + source.yaml)
│   ├── agents/            #   operational runbooks referencing policies/
│   └── dist/              #   timeline.html · transitions/ · changes/ · policies/*.pdf
├── artifacts/             # Cached PDFs, extracted markdown, diffs, change records (gitignored)
├── config/models.yaml     # Per-stage LLM model config (provider + model per stage)
├── scripts/               # Demo recording / brand overlay / voiceover helpers
├── tests/                 # pytest suite
└── docs/
    ├── superpowers/specs/         # Design docs (the canonical project spec)
    ├── superpowers/plans/         # Phase 1 implementation plan
    ├── superpowers/demo-runbook.md
    ├── blog-post-network-brand-rulebook.md
    └── demo-video-brief.md
```

## Tech stack

- **Python 3.12**, `uv` for env / dependency management.
- **PDF extraction:** `pymupdf` (body + headings) + `pdfplumber` (tables), behind an
  `Extractor` adapter so a vision-model or LlamaParse extractor can drop in if SPME
  tables come out garbled.
- **LLM:** OpenAI via the official `openai` SDK. Default model `gpt-4.1-mini`;
  per-stage overrides in `config/models.yaml`. Stable prompt prefixes (the Acme Pay
  policy repo, baseline SPME chunks) are placed first to benefit from OpenAI prompt
  caching.
- **Presentation:** `jinja2` + `redlines` (word-level prose redline) + `markdown-it-py`
  + `pygments` + `diff2html` (CDN). Plain handwritten CSS. No JS framework.
- **PDF rendering:** `pandoc` (markdown → PDF) for the baseline Acme Pay policies
  distributed to compliance staff.

## Where to read more

- **Full design:** [`docs/superpowers/specs/2026-05-07-policy-diffs-poc-design.md`](./docs/superpowers/specs/2026-05-07-policy-diffs-poc-design.md)
- **Phase 1 implementation plan:** [`docs/superpowers/plans/2026-05-07-policy-diffs-poc-phase-1.md`](./docs/superpowers/plans/2026-05-07-policy-diffs-poc-phase-1.md)
- **5-minute demo walk-through:** [`docs/superpowers/demo-runbook.md`](./docs/superpowers/demo-runbook.md)
- **Synthetic Acme Pay policy library:** [`credio-policies/README.md`](./credio-policies/README.md)

## Status

**Phase 1 (SPME) implemented.** Pipeline is artifact-agnostic; phases 2 and 3 reuse
the same code with new prompts and a wider synthetic policy library:

| Phase | Artifact | Notes |
|---|---|---|
| 1 ✅ | Security Rules and Procedures – Merchant Edition (SPME) | ~250 pp, tightest fit to Acme Pay's fraud/risk surfaces |
| 2 | Mastercard Rules | Broader scope — acquirer obligations, ECP/EFM, service providers |
| 3 | Chargeback Guide | Narrow but deep on dispute resolution; largest doc (~1,100 pp) |

Quality bar must be met on phase N before phase N+1 starts.

## Naming notes

**Acme Pay** is the fictional customer-facing brand used throughout the rendered
demo, config, READMEs, LLM prompts, code, tests, and docs.

Lowercase `credio` survives only in path-stable identifiers that would break things
if renamed: the `credio-policies/` directory, the `test_credio_baseline.py` test
file, and a few Python variable names (`credio_repo`, etc.). These are not user-visible
and can be renamed in a future cleanup pass.
