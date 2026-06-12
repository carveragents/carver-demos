# Public deployment of the gallery — design spec

**Date:** 2026-06-12 · **Status:** approved (in-conversation brainstorm)

## Goal
Publish the gallery dashboard for public consumption with: lowest maintenance,
zero cost, weekly-refreshable data, and **only aggregate data exposed** (never
the rich per-record annotations or any record identifiers).

## Trust boundary (the core of the design)

```
YOUR ENVIRONMENT (weekly run — has CARVER_API_KEY / OPENAI_API_KEY)
  pull → build aggregates + deck
       → export slim public bundle  -> data/public/
       → validate_upstream.py   (API reconciliation; key-gated)
       → validate_bundle.py     (offline: leak gate, completeness, drift)
       → git commit data/public/  ONLY IF both validators exit 0   ← blocking gate
       → push

STREAMLIT COMMUNITY CLOUD (public — ZERO secrets)
  read committed data/public/  →  render charts
  (no API calls, no OpenAI, no validation, no raw data)
```

The public app reads only `data/public/`. Raw data (`annotations.parquet`,
`annotations.jsonl`) and both API keys never leave your environment. The
validators are a **blocking gate**: a hard FAIL prevents the commit, so a bad or
leaky bundle can never reach Streamlit — the last good bundle stays live.

## Aggregate-only — what ships

The two record-level tabs (**Record Drill-Down**, **Highlight Reel**) are removed
in the public build; they are the only surfaces that read rich content / the raw
JSONL. Every other tab runs on dimensions + counts.

**`PUBLIC_KEEP_COLUMNS` (the slim annotations frame — exactly these 15):**
```
topic_id,
jurisdiction_country, jurisdiction_bloc, jurisdiction_scope,
impact_score, impact_confidence, impact_label,
urgency_score, urgency_confidence, urgency_label,
update_type,
reconciled_published_date,
richness_score,            # precomputed; constituent has_*/n_reg_* cols dropped
n_entities, n_tags
```
Everything else in `schema.NORMALIZED_COLUMNS` is stripped — all identifiers
(`artifact_id`, `entry_id`, `source_id`, timestamps), all content (`title`,
`summary`, `feed_url`, `base_url`, `*_reasoning`, `regulator_name/division/
other_agency`), detailed date columns + calendars, `relevance_*`, `update_subtype`,
`category` (internal), and every richness-constituent column. Net: each row is
`(institution, jurisdiction, scores, pub-date, counts)` — no content, no record id.

The sidecars are already aggregate and ship as-is into `data/public/`:
`topic_catalog.csv`, `topic_domains.csv`, `entity_leaderboard.csv`,
`tag_leaderboard.csv`, `entity_type_breakdown.csv`, `term_stats_meta.json`,
`snapshot_meta.json`, and the deck PDF.

## Mechanisms

- **Relocatable data dir:** `config.DATA_DIR` honours `CARVER_DATA_DIR` env. Setting
  `CARVER_DATA_DIR=data/public` makes every loader resolve to the slim bundle —
  same filenames, zero loader changes. (`annotations.parquet` is already the
  normalized frame; `load_normalized` reads it directly, so a slim parquet loads
  without re-normalization.)
- **Public build flag:** `CARVER_PUBLIC_BUILD=1` → gallery omits the two record
  tabs, guards `build_record_index`/`get_raw_record` (no JSONL access), and applies
  the loader allowlist.
- **Loader allowlist (belt-and-suspenders, structural):** the public load path
  selects `df[PUBLIC_KEEP_COLUMNS ∩ df.columns]` so the app *physically cannot*
  surface a content column even if a bad bundle were committed by hand.
- **`data/public/` is committable** (the `data/*.ext` gitignore globs are
  single-level and don't match `data/public/`). No `.gitignore` change needed.

## Validation

### Offline bundle validator (`tools/validate_bundle.py`, no key)
- **HARD GATE — leak / aggregate-only:** public parquet columns ⊆ `PUBLIC_KEEP_COLUMNS`;
  no content-denylist names; every string column `max(len) < PUBLIC_STRING_MAXLEN`.
- **HARD GATE — completeness:** row count present and not collapsed vs baseline
  (drop > X% fails); snapshot date advanced; no KEEP column 100% null; schema present.
- **HARD GATE — integrity:** parquet + sidecar CSV/JSON load and are non-empty;
  deck PDF page count/size in range; every `topic_id` resolves to the catalog.
- **WARN — drift:** vs `data/public/baseline.json` (distinct institutions/countries/
  update-types, null-rates, score means, out-of-window date share). Baseline updates
  on a passing run; thresholds are relative, not magic absolutes.
- Prints PASS/WARN/FAIL report → `data/public/validation_report.md`; **exits non-zero
  on any hard FAIL**.

### Upstream reconciliation (`tools/validate_upstream.py`, key-gated; skipped if no key)
- **HARD — institutions ↔ topics:** `len(topic_catalog) == count(/feeds/topics)`.
- **HARD — curation invariant:** `curated_rows + noise_rows == full_rows` (the
  "records minus discarded update types" identity, computed locally).
- **WARN — records ↔ upstream total:** local full rows ≈ upstream annotations total
  within a small % (the live feed drifts; use the cheap count if the API exposes one,
  else reconcile against the pull's stamped count — never pull 200k just to count).
- **WARN — freshness:** newest upstream artifact `created_at` within a few days of
  the snapshot date.
- **(bonus) referential:** distinct `topic_id`s in annotations ⊆ catalog/topics.
- Exits non-zero on a hard FAIL.

## Deployment (Streamlit Community Cloud)
- Connect repo (may be **private** — the app is public, repo can stay hidden).
- Entrypoint `apps/gallery.py`; env `CARVER_PUBLIC_BUILD=1`, `CARVER_DATA_DIR=data/public`.
- **No secrets.** Lean `requirements-public.txt` (streamlit, pandas, pyarrow, plotly,
  pycountry — no openai/httpx).

## Weekly loop (yours)
`pull → build → export_public_bundle → validate_upstream + validate_bundle →
commit data/public/ iff both pass → push` → Streamlit auto-redeploys.

## Out of scope
No CI (you run the jobs). LLM enrichment (domain/entity/regulator) runs on demand,
not weekly (slowly-changing dimensions). The internal full app is unchanged when
the flag is off.
