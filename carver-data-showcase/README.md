# Carver Annotation Data Showcase

This project demonstrates the range, quality, and richness of the Carver agents annotation dataset — the AI-generated, deeply structured regulatory intelligence Carver attaches to every feed entry: impact and urgency scores with labels and confidence, actionables across seven lanes, critical dates, impact summaries, regulatory references, entities, and jurisdiction metadata. It serves two audiences: a **Showcase Gallery** (`apps/gallery.py`) for prospective buyers who want to see the breadth, quality, and depth of the annotations across finance, data protection, and medical-device regulation worldwide; and a **Data-Quality Cockpit** (`apps/cockpit.py`) for internal QA teams who need a triage surface — coverage gaps, cleanup queues, anomaly counts, and CSV exports.

> The annotation also carries a *relevance* score, but it is a deprecated weighted sum of impact and urgency, so the Gallery does not surface it anywhere.

---

## Data foundation

The apps run entirely from a **point-in-time snapshot of the full annotation corpus** — **211,489 records** pulled on **2026-06-09** — stored at `data/annotations.jsonl` (and its cached `data/annotations.parquet`). Provenance (pull date, scope, total) is recorded in `data/snapshot_meta.json` and surfaced in both apps as a "not a live feed" note. Records by category (most-specific assignment; topics outside the three showcased categories fall to *Uncategorized*):

| Category | Records | Share |
|---|---:|---:|
| Finance | 139,347 | 65.9% |
| Uncategorized | 53,160 | 25.1% |
| Data protection & cybersecurity | 10,132 | 4.8% |
| Medical Devices | 8,850 | 4.2% |
| **Total** | **211,489** | |

This is the complete corpus — no sub-sampling — so the category mix reflects the true live distribution (Finance dominates). The snapshot covers 1,046 distinct topics, 158 countries, 11,441 distinct regulators, and 114 update types. All metrics are computed live over this snapshot — the apps never call the live API.

A **topic catalog** (`data/topic_catalog.csv`) lists all 1,071 monitored institutions with name, acronym, jurisdiction code, entity type, scope, and category, generated via `tools/pull_topic_catalog.py`.

Both data files are git-ignored. To regenerate them:

1. Add your key to `.env` (see Setup below).
2. Pull the full annotation corpus (~211K records, ~1.5 GB JSONL):
   ```
   .venv/bin/python tools/pull_full.py
   ```
3. Pull the topic catalog (1,071 institutions):
   ```
   .venv/bin/python tools/pull_topic_catalog.py
   ```

> An earlier 58,982-record **category-stratified** sample (`tools/pull_stratified.py`, Finance capped at 40K for visual balance) is retained for reference; the showcase now uses the complete corpus for honest, complete statistics.

---

## Setup

**Requirements:** Python 3.12, a Carver API key.

```bash
# 1. Create the virtual environment
python3.12 -m venv .venv

# 2. Install dependencies
.venv/bin/python -m pip install -r requirements.txt

# 3. Create .env in the repo root
echo "CARVER_API_KEY=your_key_here" > .env
```

---

## Run the apps

Both apps read from the local snapshot — no live API calls on render.

```bash
# External Showcase Gallery (Overview, Geography, Institutions, … Highlight Reel)
.venv/bin/python -m streamlit run apps/gallery.py

# Internal Data-Quality Cockpit (coverage matrix, cleanup queue, anomaly panel, field-health)
.venv/bin/python -m streamlit run apps/cockpit.py
```

---

## Tests

```bash
.venv/bin/python -m pytest -q
```

218 tests covering all pipeline modules (`config`, `schema`, `ingest`, `normalize`, `load`, `metrics`, `richness`, `quality`, `filters`) plus smoke tests for both apps. Tests never hit the live API — HTTP calls are stubbed with `httpx.MockTransport`.

---

## Architecture

```
carver_showcase/        # shared pipeline (no Streamlit dependency)
  config.py             # constants, thresholds, ISO table, richness weights
  schema.py             # NORMALIZED_COLUMNS, DTYPES, FIELD_MAP (probe-confirmed paths)
  ingest.py             # load_snapshot (stream JSONL), pull_snapshot wrappers
  normalize.py          # normalize_record / normalize_frame (empties→NA, flags, counts)
  load.py               # load_normalized (build-or-cache parquet), load_catalog
  metrics.py            # coverage_matrix, score_distributions, breadth_summary,
                        # volume_over_time, historical_depth
  richness.py           # richness_scores (weighted formula), highlight_reel
  quality.py            # predicate_flags (9 predicates), anomaly_report (11 rules),
                        # cleanup_queue

apps/
  gallery.py            # Showcase Gallery — external audience, 11 named views
  cockpit.py            # Data-Quality Cockpit — internal QA, views 7.1–7.7
  components/
    filters.py          # FilterState, sidebar_filters, apply_filters (pure, vectorized)
    render.py           # kpi_cards, snapshot_note, scope_banner,
                        # richness_definition, record_drilldown
    theme.py            # shared score-axis order + colors (impact, urgency)

tools/                  # one-time data pull scripts (not run on render)
  pull_full.py          # pulls the full annotation corpus (~211K, no sampling)
  pull_stratified.py    # earlier category-stratified pull (retained for reference)
  pull_topic_catalog.py # pulls the 1,071-institution topic catalog

data/                   # git-ignored generated files
  annotations.jsonl     # 211,489-record full corpus (~1.5 GB)
  annotations.parquet   # normalized, cached parquet (warm load <1s)
  snapshot_meta.json    # pull date + scope + total (drives the "not live" note)
  topic_catalog.csv     # 1,071 monitored institutions
  topic_categories.csv  # category→topic map (610 entries, used for joins)

tests/                  # pytest suite (218 tests)
docs/                   # reference docs and v2 roadmap
```

The pipeline is deterministic and makes no LLM calls. `carver_showcase/` feeds both apps with no duplicated logic. The Gallery and Cockpit share sidebar filter state via `apps/components/filters.py` and rendering helpers via `apps/components/render.py`. The parquet is built once from the JSONL snapshot and cached — subsequent loads are sub-second.

For planned LLM-powered enhancements deferred to v2, see [docs/v2-llm-enrichment-ideas.md](docs/v2-llm-enrichment-ideas.md).
