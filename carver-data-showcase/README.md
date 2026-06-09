# Carver Annotation Data Showcase

This project demonstrates the range, quality, and richness of the Carver agents annotation dataset — the AI-generated, deeply structured regulatory intelligence Carver attaches to every feed entry: impact/urgency/relevance scores with labels and confidence, actionables across seven lanes, critical dates, impact summaries, regulatory references, entities, and jurisdiction metadata. It serves two audiences: a **Showcase Gallery** (`apps/gallery.py`) for prospective buyers who want to see the breadth, quality, and depth of the annotations across finance, data protection, and medical-device regulation worldwide; and a **Data-Quality Cockpit** (`apps/cockpit.py`) for internal QA teams who need a triage surface — coverage gaps, cleanup queues, anomaly counts, and CSV exports.

---

## Data foundation

The apps run entirely from a **58,982-record, category-stratified snapshot** stored at `data/annotations.jsonl` (and its cached `data/annotations.parquet`). The three categories and their record counts are:

| Category | Records | Share |
|---|---:|---:|
| Finance | 40,000 | 67.8% |
| Data protection & cybersecurity | 10,132 | 17.2% |
| Medical Devices | 8,850 | 15.0% |
| **Total** | **58,982** | |

Medical Devices and Data protection were pulled in full; Finance was sub-sampled to 40,000 so one category does not dominate the breadth views. The snapshot covers 405 distinct topics, 111 countries, 3,219 distinct regulators, and 56 update types. All corpus metrics are computed over this snapshot — the apps never call the live API.

A **topic catalog** (`data/topic_catalog.csv`) lists all 1,071 monitored institutions with name, acronym, jurisdiction code, entity type, scope, and category, generated via `tools/pull_topic_catalog.py`.

Both data files are git-ignored. To regenerate them:

1. Add your key to `.env` (see Setup below).
2. Pull the annotation snapshot (category-stratified, 58,982 records):
   ```
   .venv/bin/python tools/pull_stratified.py
   ```
3. Pull the topic catalog (1,071 institutions):
   ```
   .venv/bin/python tools/pull_topic_catalog.py
   ```

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
# External Showcase Gallery (views v0–v9: breadth, quality, richness, highlight reel)
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
  gallery.py            # Showcase Gallery — external audience, views v0–v9
  cockpit.py            # Data-Quality Cockpit — internal QA, views 7.1–7.7
  components/
    filters.py          # FilterState, sidebar_filters, apply_filters (pure, vectorized)
    render.py           # kpi_cards, sampling_caveat_banner, record_drilldown

tools/                  # one-time data pull scripts (not run on render)
  pull_stratified.py    # pulls the category-stratified annotation snapshot
  pull_topic_catalog.py # pulls the 1,071-institution topic catalog

data/                   # git-ignored generated files
  annotations.jsonl     # 58,982-record snapshot (~423 MB)
  annotations.parquet   # normalized, cached parquet (warm load <1s)
  topic_catalog.csv     # 1,071 monitored institutions
  topic_categories.csv  # category→topic map (610 entries, used for joins)

tests/                  # pytest suite (218 tests)
docs/                   # reference docs and v2 roadmap
```

The pipeline is deterministic and makes no LLM calls. `carver_showcase/` feeds both apps with no duplicated logic. The Gallery and Cockpit share sidebar filter state via `apps/components/filters.py` and rendering helpers via `apps/components/render.py`. The parquet is built once from the JSONL snapshot and cached — subsequent loads are sub-second.

For planned LLM-powered enhancements deferred to v2, see [docs/v2-llm-enrichment-ideas.md](docs/v2-llm-enrichment-ideas.md).
