# Design — "State of Carver Data" downloadable deck

**Date:** 2026-06-10
**Goal:** A downloadable slide deck, one slide per dashboard tab, synced to the
current snapshot, available from a prominent link in the gallery, re-rendered on
every data pull, and always reflecting the website with **no filters applied**.

## Format decision — PDF (16:9)

A PDF is the canonical "deck you download and email around" for external
consumption: portable, offline, no app needed. Rendered with **reportlab** (pure
Python, no system deps) composing per-chart **PNG**s exported from the same
Plotly figures the site shows, via **kaleido** (verified working in this venv).

Rejected: PPTX (heavier dep, editing not needed), self-contained HTML deck
(great but less "downloadable artifact"; the site already *is* the interactive
view — the deck is the portable snapshot of it).

## Sync architecture — single source of truth for charts

The core requirement is *the deck matches the website*. We guarantee this
**structurally**, not by reimplementation:

- New module `carver_showcase/charts.py` — **pure, Streamlit-free** figure
  builders (`df → plotly.graph_objects.Figure`) plus a few prep helpers for
  caption numbers. Every chart currently built inline in `apps/gallery.py` moves
  here verbatim (same chart type, title, palette, labels).
- `apps/gallery.py` is refactored to **call these builders** for the Geography,
  Institutions, Category Structure, Update Types, Volume, Score Distributions and
  Urgency Basis tabs.
- `carver_showcase/deck.py` calls the **same builders**, so the deck cannot drift
  from the site. Metrics keep coming from the existing `carver_showcase/metrics.py`
  (already the single source of truth for numbers).

`charts.py` imports only pandas / plotly / config — no Streamlit, no kaleido — so
it is unit-testable and reusable.

## Always-unfiltered

The deck builder loads `load_normalized()` (full parquet) + `load_catalog()` +
`load_snapshot_meta()` and applies **no sidebar filters** — i.e. the site as
viewed with every filter at its default. This is the natural full-corpus state.

## Slides (one per relevant tab; Drill-Down & Highlight Reel excluded)

1. **Cover** — "State of Carver Data", snapshot date, one-line tagline, headline
   KPI strip (records · institutions · countries · regulators).
2. **Overview** — headline KPIs + historical-depth callouts (earliest/latest/span,
   recency 1y/3y/7y) with a small recency bar; "what is an annotation" one-liner.
3. **Geography** — records-by-country choropleth (hero) + top-countries callouts.
4. **Institutions** — monitored-institutions choropleth (hero) + monitored count,
   top regulator types.
5. **Category Structure** — category→institution sunburst (breadth visual) +
   per-category record counts + top institution callout.
6. **Update Types** — top-N update-type bar + long-tail callout.
7. **Volume Over Time** — yearly volume bar, 1% date floor, period-start anchored
   (matches the gallery's default view).
8. **Score Distributions** — impact + urgency histograms side by side + label-mix.
9. **Urgency Basis** — urgency-basis distribution + share.
10. **About / Methodology** — computed-live note, richness-score definition,
    date-floor & anomaly-window notes, link back to the live showcase.

Each slide carries a footer: `Carver · State of Carver Data · snapshot YYYY-MM-DD ·
computed live, nothing hard-coded · page N`.

A static sunburst over ~1,046 institutions is intentionally dense — the gestalt
*is* the breadth message; the readable numbers live in the slide's callouts. (The
interactive, zoomable sunburst remains on the site.)

## Auto-refresh

`tools/pull_full.py`, after writing the JSONL/meta and invalidating the parquet,
rebuilds the normalized frame and calls `deck.build_deck()`. The deck build is
wrapped so a rendering failure **warns but does not fail the pull** (the pull is
the critical path; the deck is a downstream artifact). A standalone
`tools/build_deck.py` regenerates on demand.

## Prominent link

A primary `st.download_button` ("📑 Download the *State of Carver Data* deck (PDF)")
at the top of the gallery header, directly under the subtitle, reading
`data/carver-state-of-data.pdf` from disk. If the file is absent (fresh checkout
before a pull), the button is replaced by a subtle caption — never an error.

## Files

- `carver_showcase/charts.py` — NEW (shared figure builders)
- `carver_showcase/deck.py` — NEW (PDF composition)
- `tools/build_deck.py` — NEW (CLI entry)
- `apps/gallery.py` — refactor to builders + download button
- `tools/pull_full.py` — call build_deck after a pull
- `carver_showcase/config.py` — add `DECK_PDF` path
- `requirements.txt` — add `kaleido`, `reportlab`
- `.gitignore` — add `data/*.pdf`
- `tests/test_charts.py`, `tests/test_deck.py` — NEW
- `docs/README.md`, `docs/LESSONS.md` — document the deck

## Out of scope

No LLM/enrichment. No new data pulled by this feature. Cockpit unchanged.
