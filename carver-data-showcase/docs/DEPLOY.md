# Deployment & Operations Guide — Carver Data Showcase

Public gallery on Streamlit Community Cloud. Weekly data refresh is manual (you run it).

---

## 1. Overview / Trust boundary

```
YOUR ENVIRONMENT  (has CARVER_API_KEY / OPENAI_API_KEY)
  pull + build aggregates + deck
    → tools/export_public_bundle.py    →  data/public/
    → tools/validate_upstream.py       (API reconciliation; key-gated)
    → tools/validate_bundle.py         (offline leak gate; no key needed)
    → git add data/public && git commit && git push   ← ONLY if both validators exit 0

STREAMLIT COMMUNITY CLOUD  (public — ZERO secrets)
  reads committed data/public/  →  renders charts
  (no API calls, no OpenAI, no raw data, no validation)
```

Your environment builds, validates, and commits the bundle. Streamlit only serves
the pre-committed `data/public/` directory. Raw data (`annotations.parquet`,
`annotations.jsonl`) and both API keys never leave your environment. The validators
are a **blocking gate**: a non-zero exit prevents the commit, so a bad or leaky
bundle can never reach Streamlit — the last good bundle stays live.

---

## 2. One-time Streamlit Community Cloud setup

1. **Connect the repo.** A private repo is fine — the app is public, the repo can
   stay hidden. In Streamlit Cloud: New app → connect GitHub → select this repo.

2. **Main file path:** `apps/gallery.py`

3. **Python version:** 3.12 (matches the dev `.venv`; no `.python-version` file in
   the repo — set this explicitly in Streamlit Cloud's Advanced settings).

4. **Requirements file:** name it `requirements-public.txt` in the repo root.
   Streamlit Cloud auto-detects `requirements.txt` by default; to use the public
   file, either:
   - **Rename strategy:** rename `requirements-public.txt` to `requirements.txt`
     before connecting (and document the swap), **or**
   - **Streamlit Cloud Advanced settings:** point the requirements file path at
     `requirements-public.txt` (available in the app's Settings → General).

5. **Environment variables / secrets** — set in App settings → Secrets (TOML format)
   or Environment variables:

   ```
   CARVER_PUBLIC_BUILD = "1"
   CARVER_DATA_DIR     = "data/public"
   ```

   **No API keys are needed.** The public app reads only the committed parquet and
   sidecar files — it makes no API calls and uses no OpenAI.

---

## 3. The data bundle

`data/public/` contains the full public bundle, committed to the repo:

| File | Contents |
|------|----------|
| `annotations.parquet` | Slim 15-column annotations frame (no identifiers, no content prose) |
| `topic_catalog.csv` | Monitored institutions catalog |
| `topic_domains.csv` | LLM-assigned institution domain classification |
| `entity_type_breakdown.csv` | Entity-type aggregate |
| `entity_leaderboard.csv` | Top entities by mentions |
| `tag_leaderboard.csv` | Top tags by count |
| `term_stats_meta.json` | Entity/tag corpus provenance |
| `snapshot_meta.json` | Pull date, scope, record count |
| `carver-state-of-data.pdf` | Pre-built deck (one slide per view) |
| `validation_report.md` | Last validator output |
| `baseline.json` | Drift baseline for the validator |

**`data/public/` is committed to git.** The `.gitignore` uses single-level glob
patterns (`data/*.parquet`, `data/*.csv`, etc.) that match only files directly in
`data/`, not in `data/public/`. No `.gitignore` change is needed.

---

## 4. Weekly refresh loop (operator runbook)

Run these commands in order from the repo root each week:

```bash
# 1. Pull fresh data and rebuild aggregates + deck
#    (your existing pull/build commands — produces data/annotations.parquet, sidecars, PDF)
python tools/pull_full.py          # or pull_stratified.py / pull_topic_catalog.py etc.
python tools/build_deck.py         # re-renders the PDF deck

# 2. Export the slim public bundle into data/public/
python tools/export_public_bundle.py

# 3. Validate: API reconciliation (needs CARVER_API_KEY)
python tools/validate_upstream.py

# 4. Validate: offline gate (no key needed — checks for leaks, drift, completeness)
python tools/validate_bundle.py

# 5. Commit ONLY if both validators exited 0:
python tools/validate_bundle.py && python tools/validate_upstream.py \
    && git add data/public \
    && git commit -m "data: weekly public bundle refresh" \
    && git push
```

**Blocking-gate logic:** both validators exit non-zero on any hard FAIL
(leak detected, schema violation, row count collapsed, referential integrity broken).
The compound `&&` chain means a single FAIL stops the commit — Streamlit keeps
serving the last good bundle. Warnings (drift, freshness) let the commit through
but are printed to stdout and written to `data/public/validation_report.md`.

`data/public/validation_report.md` and `data/public/baseline.json` are written by
`validate_bundle.py` and are committed as part of `git add data/public`. The
baseline updates on each passing run so drift thresholds track the evolving corpus
rather than hardcoded absolutes.

---

## 5. Local preview of the public build

Before pushing, sanity-check the public app locally:

```bash
CARVER_PUBLIC_BUILD=1 CARVER_DATA_DIR=data/public \
    .venv/bin/streamlit run apps/gallery.py
```

This runs the gallery in public mode against the just-exported `data/public/`
bundle — the same configuration Streamlit Cloud will use. Verify the two
record-level tabs (Record Drill-Down, Highlight Reel) are absent, and that the
scope banner shows the correct record count.

---

## 6. What is NOT exposed

The public build enforces an aggregate-only guarantee through three independent layers:

- **`CARVER_PUBLIC_BUILD=1`** — gallery code removes the Record Drill-Down and
  Highlight Reel tabs; `build_record_index` / `get_raw_record` are never called
  (no JSONL access).
- **15-column allowlist** (`PUBLIC_KEEP_COLUMNS` in `config.py`) — `load_normalized`
  applies `keep_columns` as a structural filter; the app physically cannot surface a
  content column even if a misconfigured bundle is deployed.
- **Offline validator HARD gates** — `validate_bundle.py` enforces: public parquet
  columns must be a subset of `PUBLIC_KEEP_COLUMNS`; no column from the content
  denylist (`title`, `summary`, `feed_url`, `artifact_id`, etc.) may be present;
  every string value must be under `PUBLIC_STRING_MAXLEN` bytes. Any violation
  exits non-zero and blocks the commit.

Each row in the public annotations frame is `(institution, jurisdiction, scores,
pub-date, counts)` — no content, no record identifier, no regulator name.
