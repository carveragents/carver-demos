# Carver Annotation Data Showcase — v1 Feature Spec / Design Doc

**Stage:** 01-spec · **Status:** draft for review
**Scope of this document:** the *design* of the v1 showcase — what each app does, what it shows,
the shared pipeline beneath them, the normalized schema, and every load-bearing design decision.
The dependency-ordered build plan and the file-by-file change list are **Stage 02** and are
deliberately not in this document.

---

## 1. Problem, audiences & scope

### 1.1 The problem

Carver attaches an AI-generated, deeply-structured **annotation** to every raw regulatory feed
entry. The raw entry is little more than a title, a link, and a date; the annotation turns it into
a machine-readable compliance object (three scored axes, a 5-part impact narrative, seven lanes of
actionables, calendar-aware critical dates, entities, tags, regulatory references, impacted
business and functions, penalties, and a structured jurisdiction classification). That value is
invisible in a list of links. This showcase makes the **range, quality, and richness** of the
annotation dataset immediately tangible — to two distinct audiences with two distinct jobs.

### 1.2 Two audiences → two prototypes → one pipeline

| | **(A) Showcase Gallery** | **(B) Data-Quality Cockpit** |
|---|---|---|
| **Audience** | External data clients (data merchants, firms buying regulatory feeds) | Carver's internal data-quality / cleanup team |
| **Job to be done** | Decide whether this feed is worth buying — is it broad, accurate, and deep? | Find and triage the records that need cleanup; track coverage and migration debt |
| **North-star question it answers** | "Is there a lot here, is it trustworthy, and how deep does each record go?" | "Where is the data thin, wrong, or inconsistent, and which records do I fix first?" |
| **Tone** | Polished, persuasive, exploratory | Diagnostic, exhaustive, actionable |

Both apps are **separate Streamlit entrypoints** that read the **same** normalized snapshot
produced by **one** shared `ingest → normalize → metrics` pipeline (§3). Coverage percentages,
score distributions, and field-population facts come from one shared metrics module so the two
apps can never disagree about what the data contains.

### 1.3 Out of scope (v1)

- Pulling new data or changing the API route — the snapshot already exists (§2.2).
- **Any LLM-backed feature.** Every derived signal in v1 is deterministic (§5). LLM-worthy ideas
  are captured in `docs/v2-llm-enrichment-ideas.md` (§10), not built.
- Deployment/hosting beyond `streamlit run` locally.
- Live API calls on render — apps read the local snapshot only (§2.2, §9.1).
- **Deferred to Stage 02 (not this stage):** the phased build plan, the file-by-file creation
  list, ready-to-run code, exact function bodies, the test-by-test list, and the final
  chart-library pick (candidate named in §9.4).

### 1.4 Audience fit is a design constraint, not an afterthought

Every app-level decision in §6 and §7 is justified against *its* audience and the two are never
blurred into one generic dashboard. The Gallery optimizes for a prospective buyer's trust and
sense of depth (curated highlights, beautiful drill-down, breadth visuals); the Cockpit optimizes
for a cleanup operator's throughput (failing-record queue, CSV export, per-rule counts with
click-through). A feature that serves one audience is not duplicated into the other unless it
genuinely serves both (e.g., score distributions appear in both, but framed differently — §7.5).

---

## 2. Data foundation

### 2.1 What an annotation is (the object the apps render)

`artifact.output_data` **is** the annotation. The verified live payload (confirmed against a
sample record, and richer than the public docs) has this shape:

```
output_data
├─ entry_id                                   # feed-entry id (join key)
├─ scores
│  ├─ impact     { label, score, confidence }
│  ├─ urgency    { basis, label, score, confidence }   # only urgency carries `basis`
│  └─ relevance  { label, score, confidence }
├─ metadata
│  ├─ tags[]                                  # free-text topic tags
│  ├─ entities[]                              # named people / bodies / firms
│  ├─ actionables { policy_change, status_change, process_change,
│  │                training_change, reporting_change, tech_data_change, other_change }  # 7 lanes
│  ├─ critical_dates
│  │  ├─ effective_date / compliance_date / comment_deadline /
│  │  │  early_adoption_date / updated_date        # each with a paired *_calendar
│  │  ├─ pub_date_content (+ pub_date_calendar)
│  │  └─ other_dates[] { date, calendar, description }
│  ├─ impact_summary { objective, what_changed, why_it_matters,
│  │                   risk_impact, key_requirements[] }   # key_requirements is a LIST
│  ├─ reg_references { rules[], statutes[], other_ref[],
│  │                   personnel[], precedents[], past_release[] }   # 6 lanes
│  ├─ impacted_business { industry, type, jurisdiction, other_notes }
│  ├─ impacted_functions[]
│  └─ penalties_consequences                  # penalties / consequences
├─ classification
│  ├─ update_type, update_subtype
│  ├─ regulatory_source { name, division_office, other_agency }
│  └─ jurisdiction { scope, country, bloc, locality, region_*, reasoning }
└─ reconciled_published_date { value, source, converted, original_calendar, valid }
```

The surrounding **envelope** carries `id` (artifact id), `topic_id`, `state`, `source_id`,
`artifact_type_id`, and timestamps; `input_data.extracted_metadata` carries the source document's
`title`, `url`, `feed_id`, `source_type`, `language` (when present), and asset list. The design
pulls the join keys, state, and timestamps from the envelope and the source title/URL from
`input_data` — see the schema in §4.

> **Assumption A1 (score ranges).** Observed scores sit on a **0–10** axis (e.g. impact 9,
> relevance 5.5, urgency 1.0) and confidences on **0–1** (e.g. 0.9, 0.85). v1 treats `[0,10]` /
> `[0,1]` as the valid ranges; values outside are flagged as anomalies (§5.3). This is stated
> explicitly because the range is inferred from the payload, not documented.

> **Assumption A2 (label↔score bands).** For the calibration / mismatch checks v1 defines a
> deterministic band convention: `low = [0,4)`, `medium = [4,7)`, `high = [7,10]`. This convention
> is consistent with the sample (urgency low@1.0, relevance medium@5.5, impact high@9). It is a
> *checking* convention, used only to surface label/score disagreement — it never rewrites a
> stored label.

### 2.2 The snapshot, its source, and its honest scope

- **Source of record.** Data was pulled **once** via the **direct Carver Artifacts API**
  (`/api/v1/artifacts/dags/{dag}/artifacts`, `artifact_type_id=annotations-v1`,
  DAG `7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad`, `X-API-Key`, offset-paginated) to a local snapshot
  `data/annotations.jsonl`. **Not** the `carver-feeds-sdk`. The puller is a one-time tool; the
  apps **never** call the live API on render (§9.1).
- **Size.** **~60,000 records** — squarely inside the required **30K–100K** band. All corpus
  metrics in both apps are computed over this snapshot.
- **Scope honesty (load-bearing).** The 60K snapshot is a **contiguous offset slice**, *not* a
  uniform random sample. It covers **403 of the ~1,087** corpus topics. Therefore:
  - Corpus-wide breadth claims ("1,087 topics, 241 jurisdictions") describe the **full dataset**
    and are labelled as such.
  - Every *live* metric the apps compute (counts, coverage %, distributions) is over the **60K
    slice** and is labelled as such.
  - Both apps show a persistent **sampling-caveat banner** on their overview stating the slice
    size, the topic coverage (403/1,087), and that the slice is contiguous, not random. This is
    part of the honest-coverage stance (§8) and is non-negotiable.
- **Build on `classification.jurisdiction`.** The deprecated `classification.jurisdiction_tier`
  is *not* a design input. It still lingers in ~1,513 records (2.5%) because the
  ~2026-06-11 backfill is incomplete; v1 treats its presence purely as a **migration-debt signal**
  in the Cockpit (§7.7), never as a jurisdiction source.

### 2.3 Representative coverage (computed, not assumed)

The metrics module computes real population % over the snapshot at load time (§8). Representative
figures from an offline coverage probe over the full 60K — used here to size the design honestly,
**not** hard-coded into the UI — are:

| Field group | Real population (60K slice) |
|---|---|
| Score trio (impact/urgency/relevance: label+score+confidence) | ≈ 100% |
| `urgency.basis` | ≈ 99.96% |
| `impact_summary.{objective, what_changed, why_it_matters, risk_impact}` | ≈ 85% |
| `impact_summary.key_requirements` | ≈ 78% |
| `tags` / `entities` | 86% / 92% |
| `impacted_business.industry` / `impacted_functions` | 83% / 83% |
| `penalties_consequences` | 56% |
| `effective_date` / `compliance_date` / `comment_deadline` | 25% / 8% / 6.5% |
| `other_dates` | 45% |
| `reg_references.rules` / `.statutes` | 22% / 35% |
| `feed_url` (source linkability) | ≈ 50% |
| `jurisdiction.country` present | ≈ 88% (12% missing) |
| `update_type` present | ≈ 99.3% |

Breadth in the slice: **403 topics · 118 countries · 42 blocs · 5 jurisdiction scopes · 3,109
distinct regulator names · 111 distinct `update_type` values.** Label mixes: impact
medium 42% / low 29% / high 29%; urgency.basis no_future_date 60% / past_deadline 37% /
future_deadline 2% / effective_immediately 0.8%.

These numbers also justify the Cockpit's specific checks (§5.3, §7): the date sparsity, the
`update_type`/regulator cardinality sprawl, the partial backfill, and the 50% feed-url linkability
are real, measurable quality stories — not invented ones.

---

## 3. Architecture & module boundaries

One shared pipeline, two app entrypoints, small single-purpose modules that are each unit-testable
in isolation.

```
            ┌──────────────────────── shared pipeline (package: carver_showcase) ─────────────────────┐
            │                                                                                          │
 data/annotations.jsonl ──> ingest ──> normalize ──> data/annotations.parquet                         │
 (one-time pull via       (load)     (flatten,       (persisted normalized frame)                      │
  Artifacts API)                      empties→NA,            │                                          │
                                      flags+counts)          ▼                                          │
                                                       load (cached)  ──>  pandas.DataFrame (the frame) │
                                                          │   │   │                                     │
                                          ┌───────────────┘   │   └───────────────┐                    │
                                          ▼                   ▼                   ▼                     │
                                       metrics            richness             quality                 │
                                  (coverage, dists,   (richness_score,    (predicates, anomaly         │
                                   breadth, time)      highlight reel)      rules, cleanup queue)       │
            └──────────────────────────────────────────────────────────────────────────────────────────┘
                                          │                   │                   │
                       ┌──────────────────┴───────────────────┴───────────────────┴──────────────────┐
                       ▼                                                                               ▼
            apps/gallery.py  (A external)                                          apps/cockpit.py  (B internal)
                       │                                                                               │
                       └──────────────── apps/components/* (shared filters, KPI cards, drill-down) ────┘
```

### 3.1 Modules and their contracts

All pipeline modules live in one importable package (`carver_showcase/`). Each has a single
responsibility and a narrow interface (illustrative signatures — exact bodies are Stage 02):

| Module | Responsibility | Key interface (in → out) |
|---|---|---|
| `config.py` | Constants only: paths, API params, the placeholder set, score/confidence ranges, label bands, plausible-date window, richness weights, prose-length thresholds, rare-`update_type` cutoff. | module-level constants |
| `ingest.py` | (a) one-time `pull_snapshot(...)` over the Artifacts API; (b) `load_snapshot(path) -> Iterator[dict]` streaming raw envelopes from the JSONL. | `pull_snapshot(api_key, dag, out_path, page_size) -> int`; `load_snapshot(path: Path) -> Iterator[dict]` |
| `schema.py` | The **single source of truth** for the normalized schema: the ordered column list, dtypes, and the extraction map (nested path → column). No logic. | `NORMALIZED_COLUMNS: list[str]`, `FIELD_MAP`, `DTYPES` |
| `normalize.py` | Flatten one raw record → one flat row per `schema`; apply empties→NA; compute presence flags and counts. | `normalize_record(raw: dict) -> dict`; `normalize_frame(records: Iterable[dict]) -> DataFrame` |
| `load.py` | App-facing cached loader: build-or-load the parquet from the JSONL, return the frame. The only thing the apps import to get data. | `load_normalized(parquet_path, jsonl_path) -> DataFrame` (wrapped in `st.cache_data` at the app edge) |
| `metrics.py` | Audience-neutral aggregates shared by both apps: coverage matrix, score/confidence distributions, breadth summary, volume-over-time. **Single source of coverage truth.** | `coverage_matrix(df, slice_by=None) -> DataFrame`; `score_distributions(df) -> dict`; `breadth_summary(df) -> dict`; `volume_over_time(df, freq) -> DataFrame` |
| `richness.py` | Gallery curation: the deterministic richness score + highlight-reel selection. | `richness_scores(df) -> Series`; `highlight_reel(df, n, diversify=True) -> DataFrame` |
| `quality.py` | Cockpit logic: per-record quality predicates, anomaly/consistency rules, the cleanup queue. | `predicate_flags(df) -> DataFrame[bool]`; `anomaly_report(df) -> dict[str, DataFrame|int]`; `cleanup_queue(df, predicates=None) -> DataFrame` |
| `apps/components/filters.py` | Shared sidebar filter state + `apply_filters(df, state) -> DataFrame` (pure). Used by both apps. | `FilterState`, `apply_filters(df, state) -> DataFrame` |
| `apps/components/render.py` | Shared Streamlit render helpers (KPI cards, the full single-record drill-down, sampling-caveat banner). | render functions taking a row/DataFrame |
| `apps/gallery.py` | (A) external entrypoint — view inventory in §6. | `streamlit run apps/gallery.py` |
| `apps/cockpit.py` | (B) internal entrypoint — view inventory in §7. | `streamlit run apps/cockpit.py` |
| `tools/coverage_probe.py` | Offline coverage/anomaly report to console/markdown (not imported by apps). | CLI |

**Why this split.** `metrics` is audience-neutral and shared; `richness` is Gallery-only;
`quality` is Cockpit-only. Each computes over the same normalized frame and never re-reads or
re-flattens raw JSON, so ingest/normalize logic exists exactly once (no per-app duplication —
hard constraint). `schema.py` holds the column contract so `normalize`, `metrics`, the apps, and
the tests all agree on names.

### 3.2 Data flow at runtime

1. First app launch builds `annotations.parquet` from the JSONL via `normalize_frame` (once).
2. `load.load_normalized` returns the cached frame (`st.cache_data`).
3. The sidebar produces a `FilterState`; `apply_filters` yields the working subset.
4. Each view calls `metrics` / `richness` / `quality` on the (cached) subset and renders.
5. No live API, ever, at steps 1–5 except the one-time offline pull that created the JSONL.

---

## 4. The normalized record schema

Each annotation becomes **one flat analytics row**. Nested `output_data.metadata.*`,
`output_data.classification.*`, `output_data.scores.*`, the envelope, and
`input_data.extracted_metadata.*` are mapped down to predictable scalar columns plus
presence-flags and counts. Persisted as **parquet** (`data/annotations.parquet`) for fast,
typed, columnar loads.

### 4.1 Normalization rules (apply uniformly during flattening)

- **Empties → NA.** Empty string `""`, whitespace-only, empty list/dict, and a small placeholder
  set (`"N/A"`, `"null"`, `"none"`, `"-"`, `"unknown"`, case-insensitive — defined in
  `config.PLACEHOLDERS`) are normalized to missing (`pd.NA` / `NaN`). This rule is what makes
  coverage % honest: a present-but-empty field counts as *missing*, not *populated*.
- **Counts** are computed *after* the empties→NA pass (an actionable lane of `""` is not counted).
- **Flags** are booleans derived from the same rule (`has_x = value is not NA`).
- **Dates** are parsed to `datetime` where possible; unparseable date strings are retained as raw
  text in a `*_raw` companion only where needed for the Cockpit (otherwise NA), and the parse
  failure itself is an anomaly signal (§5.3).
- **Nested-path mapping** is declared once in `schema.FIELD_MAP` (e.g.
  `output_data.scores.impact.score → impact_score`), so the mapping is data, not scattered code.

### 4.2 Columns

**Identity / join keys / envelope**
`artifact_id` (envelope `id`), `entry_id` (`output_data.entry_id`), `topic_id`, `source_id`,
`state`, `artifact_created_at`, `artifact_updated_at`.

**Scores (3 axes)**
`impact_label`, `impact_score`, `impact_confidence`;
`urgency_label`, `urgency_score`, `urgency_confidence`, `urgency_basis`;
`relevance_label`, `relevance_score`, `relevance_confidence`.

**Classification**
`update_type`, `update_subtype`,
`regulator_name` (`regulatory_source.name`), `regulator_division` (`division_office`),
`regulator_other_agency` (`other_agency`),
`jurisdiction_scope`, `jurisdiction_country`, `jurisdiction_bloc`, `jurisdiction_locality`,
`jurisdiction_region`, `jurisdiction_reasoning`,
`has_jurisdiction_tier_legacy` (flag only — deprecated field still present; Cockpit migration check).

**Category** (range dimension — see Assumption A3)
`category` — resolved by deterministic priority: (1) `output_data.classification.category` if it
exists; else (2) a static, optional sidecar `data/topic_categories.csv` (`topic_id → category`,
left-joined); else (3) `"Uncategorized"`. The coverage matrix reports `category` population so the
gap is visible, never hidden.

**Source document (from `input_data.extracted_metadata`)**
`title`, `feed_url` (the source/document URL; ≈50% populated), `base_url` (deterministic
registrable domain parsed from `feed_url`), `language` (if present, else NA), `source_type`,
`summary` (if a source summary field is present, else NA — population reported, not assumed).

**Key dates (each value + paired `*_calendar`)**
`effective_date`, `compliance_date`, `comment_deadline`, `early_adoption_date`, `updated_date`,
`pub_date_content`; `n_other_dates` (length of `other_dates[]`).

**Reconciled published date (+ provenance)**
`reconciled_published_date` (parsed datetime), `reconciled_pub_source`,
`reconciled_pub_converted`, `reconciled_pub_original_calendar`, `reconciled_pub_valid` (bool).

**Richness counts & flags**
`n_tags`, `n_entities`;
`n_actionable_lanes` (0–7, non-empty lanes among the 7);
`has_impact_summary` plus `has_objective`, `has_what_changed`, `has_why_it_matters`,
`has_risk_impact`, `n_key_requirements`;
`n_reg_rules`, `n_reg_statutes`, `n_reg_other_ref`, `n_reg_personnel`, `n_reg_precedents`,
`n_reg_past_release`, `n_reg_refs_total` (sum of the 6 ref lanes);
`has_impacted_business`, `n_impacted_functions`;
`n_penalties` / `has_penalties`;
`n_critical_dates` (count of populated key date types + `n_other_dates`);
`richness_score` (0–100, computed by `richness.py` — §5.2).

> **Assumption A3 (category source).** Category is a corpus organizing principle (3 categories:
> Data protection & cybersecurity, Finance, Medical Devices) and is **not guaranteed present** in
> the annotation payload (the data-access constraint gives us only the annotations snapshot). v1
> resolves `category` by the priority above and **measures** its population in the coverage matrix.
> If neither the field nor the sidecar is available, category-sliced views render with an explicit
> "category unavailable for this slice" note rather than fabricating a value. This keeps the
> design honest and removes a hidden dependency.

### 4.3 Representative column definitions (to pin conventions)

- `n_actionable_lanes` *(int 0–7)*: `sum(1 for lane in ACTIONABLE_LANES if not is_missing(value))`
  over the 7 lanes `{policy, status, process, training, reporting, tech_data, other}_change`.
- `coverage(field)` *(float 0–1, in metrics)*: `df[field].notna().mean()` after empties→NA — i.e.
  the fraction of rows where the field is genuinely populated.

---

## 5. Deterministic derived signals (no LLM, provably)

Every "smart" feature is a concrete formula or threshold rule over the normalized frame. There is
no model call anywhere in v1. Each subsection below names the place an LLM would be tempting and
states the deterministic v1 choice; the LLM versions are logged in §10.

### 5.1 Empties, counts, flags
Already defined (§4.1). Pure, vectorized pandas. *(LLM temptation: "is this field meaningfully
populated?" → v1 uses the explicit placeholder set + length, not a judgment model.)*

### 5.2 Richness score (Gallery curation) — deterministic, bounded 0–100

A weighted blend of populated rich components, each normalized to `[0,1]`, weights summing to 1,
scaled ×100 and rounded:

| Component | Weight | Normalized value |
|---|---|---|
| Prose depth | 0.30 | (# of 5 `impact_summary` parts present) / 5 |
| Actionables | 0.20 | `n_actionable_lanes` / 7 |
| Critical dates | 0.15 | `min(n_critical_dates, 5)` / 5 |
| Regulatory refs | 0.15 | `min(n_reg_refs_total, 6)` / 6 |
| Entities & tags | 0.10 | `(min(n_entities,8)/8 + min(n_tags,8)/8) / 2` |
| Impacted business/functions | 0.10 | `(has_impacted_business + (n_impacted_functions>0)) / 2` |

`richness_score = round(100 × Σ weightᵢ × valueᵢ)`. Properties used by tests (§9.3): bounded
`[0,100]`, monotonic non-decreasing as any component gains population, and explainable (each
record can show its component breakdown). Weights live in `config.RICHNESS_WEIGHTS` so they are
one constant, not scattered magic numbers. *(LLM temptation: "rate how impressive this record is"
→ v1 uses this transparent weighted-coverage formula.)*

**Highlight reel.** `highlight_reel(df, n, diversify=True)` = the top-`n` rows by
`richness_score` **desc**, tie-broken by `impact_score` desc then `artifact_id` (fully
deterministic, stable). With `diversify=True`, a one-pass filter keeps at most one record per
`topic_id` (then per `update_type`) until `n` is reached, so the reel isn't all one topic. No
randomness, no model — reproducible across runs. *(LLM temptation: "pick the most interesting
examples" → v1 = deterministic top-N by the richness formula with a diversity pass.)*

### 5.3 Quality predicates & anomaly rules (Cockpit) — deterministic

**Per-record quality predicates** (each a boolean column from `predicate_flags`; a record failing
≥1 enters the cleanup queue, §7.2):

| Predicate | Rule | Expected hit-rate (probe) |
|---|---|---|
| `missing_core_score` | any of the 3 axes' label/score/confidence is NA | ≈ 0% |
| `missing_join_key` | `topic_id` or `entry_id` NA | tiny (33 records missing topic_id) |
| `missing_feed_url` | `feed_url` NA → not back-linkable for triage | ≈ 50% |
| `missing_jurisdiction_country` | `jurisdiction_country` NA | ≈ 12% |
| `missing_update_type` | `update_type` NA | ≈ 0.7% |
| `no_impact_summary` | all 5 `impact_summary` parts NA | from prose ≈85% pop → ≈15% |
| `short_prose` | any present prose part shorter than `config.MIN_PROSE_CHARS` (e.g. 40) | measured |
| `no_actionables` | `n_actionable_lanes == 0` | measured |
| `empty_but_expected` | high impact/relevance label but `no_impact_summary` or `no_actionables` | measured |

**Anomaly & consistency rules** (each from `anomaly_report` → count + drill-down frame):

| Rule | Definition | Grounding |
|---|---|---|
| `score_out_of_range` | any score ∉ `[0,10]` or confidence ∉ `[0,1]` | A1 |
| `label_score_mismatch` | a score's `label` disagrees with its band (A2) | calibration |
| `date_order_inconsistency` | e.g. `comment_deadline > effective_date`, or `compliance_date < effective_date`, when both present | logical |
| `implausible_pub_date` | `reconciled_published_date` ∉ `config.PLAUSIBLE_DATE_WINDOW` (e.g. `[1990-01-01, today+2y]`) | probe found 1947-12-25 … 2105-07-01 |
| `invalid_reconciled_date` | `reconciled_pub_valid == False` | 9 records |
| `duplicate_entry_id` | `entry_id` occurs >1× in snapshot | dedup |
| `invalid_jurisdiction_country` | `jurisdiction_country` not NA but not in the static ISO-3166 name/code set (`config`) | 12% missing + validity |
| `residual_legacy_field` | `has_jurisdiction_tier_legacy == True` | 1,513 records (2.5%) — backfill debt |
| `update_type_rare` | `update_type` whose snapshot frequency < `config.RARE_UPDATE_TYPE_CUTOFF` | 111 distinct values (sprawl) |
| `regulator_near_duplicate` | rows whose `regulator_name`, after deterministic canonicalization (lowercase, strip punctuation/whitespace, drop legal suffixes like "Inc/Ltd/Authority"), collapse with ≥1 other distinct raw name | 3,109 distinct names |
| `unparseable_date` | a non-empty date string that failed parsing | parse signal |

*(LLM temptation: "are these two regulator names the same body?" / "is this label right?" →
v1 uses deterministic canonicalization + band rules + a static country list, not a matcher model.
The fuzzy/semantic versions are explicit v2 items, §10.)*

### 5.4 Field-health / cardinality summary
`update_type` distinct-count vs an expected handful (sprawl alert + the rare-value list);
`regulator_name` distinct-count and the near-duplicate canonical grouping (dedup candidate
surface); `jurisdiction_country` validity rate. All counts/group-bys — no model.

---

## 6. (A) Showcase Gallery — external clients

**Goal:** make range, quality, and richness immediately tangible and explorable to a buyer.
Aggregate views prove **range**; score views prove **quality**; the single-record drill-down and
highlight reel prove **richness**. Each view below states what it proves to a buyer.

### 6.1 Sidebar filters (drive every view)
`category`, `jurisdiction` (country / bloc / scope), `regulator`, `update_type`, `impact` /
`urgency` / `relevance` score ranges (sliders), `reconciled_published_date` range, and a
`min richness_score` slider. Filters produce a `FilterState`; `apply_filters` yields the working
subset that **all** views below render from. This is the interactivity that makes it a live tool,
not a static report. (Implausible-date records are excluded from time-axis views by default with a
toggle to include them.)

### 6.2 View inventory

| # | View | Proves | What it shows |
|---|---|---|---|
| 0 | **Overview & "What is an annotation" explainer** | the pitch | Plain-language explainer of the annotation object with one annotated real example; **headline KPIs** (annotations in slice ≈60K, topics 403, countries 118, regulators, update_types, % with full score trio, median richness); the **sampling-caveat banner** (§2.2). |
| 1 | **Jurisdiction & geography breadth** *(RANGE)* | global reach | Country choropleth + bloc/scope breakdown; counts of distinct countries/blocs in the current filter. |
| 2 | **Category → topic structure** *(RANGE)* | taxonomic breadth | Sunburst/treemap `category → topic`; topic-volume bars. Degrades gracefully if `category` unavailable (A3). |
| 3 | **Update-type mix** *(RANGE)* | event-type variety | Distribution of `update_type` (top-N + explicit long-tail count, tying to the sprawl story honestly). |
| 4 | **Volume over time** *(RANGE)* | temporal coverage & recency | Annotations per month/quarter by `reconciled_published_date` (implausible dates excluded by default). |
| 5 | **Score distributions** *(QUALITY)* | scored, not guessed | Histograms of impact/urgency/relevance `score`, with `confidence` overlay and `label` mix. |
| 6 | **Urgency basis breakdown** *(QUALITY)* | reasoning is explicit | Bar of `urgency_basis` (no_future_date / past_deadline / future_deadline / effective_immediately). |
| 7 | **Label-vs-score calibration** *(QUALITY)* | internal consistency | Per-axis heatmap of `label` band × numeric `score`; mismatches (A2) are visible but framed as "calibration", with the count linking to the Cockpit's rule. |
| 8 | **Single-record richness drill-down** *(RICHNESS)* | depth per record | Select a record (search or from the reel) and render the **full** nested annotation beautifully — see §6.3. |
| 9 | **Highlight reel** *(RICHNESS)* | "the best of it", honestly curated | Auto-selected top-N by deterministic `richness_score` (§5.2) within current filters; cards link into the drill-down. |

### 6.3 The single-record drill-down (the richness centerpiece)

Renders, in a designed layout, every populated part of one annotation and **hides empty sections**
(honest — no blank scaffolding):

- **Header:** title, regulator (name + division), jurisdiction (country/bloc/scope), update_type /
  subtype, reconciled published date, source link (`feed_url`).
- **Scores:** three gauges (impact / urgency / relevance) showing `score`, `label`, `confidence`;
  urgency also shows `basis`.
- **Impact summary:** the 5 parts — objective, what_changed, why_it_matters, risk_impact, and the
  `key_requirements` list.
- **Actionables:** the 7 lanes as labelled cards (only populated lanes shown).
- **Critical dates:** a small timeline of the key dates (with calendars) plus the `other_dates[]`
  list with descriptions.
- **Entities & tags:** chip rows.
- **Regulatory references:** the 6 lanes (rules / statutes / other_ref / personnel / precedents /
  past_release).
- **Impacted business & functions:** industry / type / jurisdiction / other_notes, and the
  functions list.
- **Penalties & consequences.**
- **Jurisdiction reasoning:** the `reasoning` narrative, showing the classification isn't a bare
  code.

This single screen is the strongest "richness" argument — it turns one row into a full compliance
brief, which is exactly the value a buyer can't see in a list of links.

---

## 7. (B) Data-Quality Cockpit — internal QA team

**Goal:** give the cleanup team an actionable triage surface — find what's missing/unclear/
inconsistent, see coverage by slice, catch anomalies, and export the bad records. Mapped to
**coverage / gaps / anomalies / triage**. Each view states the QA action it enables.

### 7.1 Coverage matrix *(coverage)*
Table: **rows = fields** (grouped: scores, classification, source, prose, dates, refs, richness),
**columns = population %** overall **and sliced by** `category` / `update_type` / `jurisdiction`
(slice dimension selectable). Heatmap coloring (red = sparse). This is the honest map of where the
data is thin — it will show scores ≈100%, prose ≈85%, dates 8–25%, refs 22–35%, feed_url ≈50%,
country ≈88%. **QA action:** see at a glance which fields/slices to prioritize.

### 7.2 Gap finder / cleanup queue *(triage)*
A **filterable, CSV-exportable** table of records failing ≥1 quality predicate (§5.3). Columns:
`artifact_id`, the list of failed predicates, the key offending fields, and `feed_url` as a
clickable triage link (rows lacking `feed_url` are flagged as harder-to-action — the 50%
linkability limitation, surfaced honestly). Filters: by predicate, category, update_type,
jurisdiction. **QA action:** work a concrete worklist, export it, open the source to fix it.

### 7.3 Anomaly & consistency panel *(anomalies)*
One row per deterministic rule (§5.3) with its **count** and a **drill-down** to the offending
records: `score_out_of_range`, `label_score_mismatch`, `date_order_inconsistency`,
`implausible_pub_date`, `invalid_reconciled_date`, `duplicate_entry_id`,
`invalid_jurisdiction_country`, `residual_legacy_field`, `update_type_rare`,
`regulator_near_duplicate`, `unparseable_date`. **QA action:** triage by rule, biggest-count first.

### 7.4 Field-health / cardinality *(anomalies)*
`update_type` cardinality (111) with the **rare-value review list**; `regulator_name` near-dup
**canonical grouping** (3,109 raw → N canonical, each group expandable) as the dedup-candidate
surface; `jurisdiction_country` validity. **QA action:** spot taxonomy sprawl and pick
merge/canonicalization candidates.

### 7.5 Distribution / outlier views *(anomalies)*
The same score distributions as the Gallery, **re-framed for QA**: look for spikes at 0/10,
degenerate confidence clustering, a prose-length distribution to find suspiciously-short entries,
and a richness-score distribution to find "empty-shell" records (low richness despite high
impact). **QA action:** find systematic, not one-off, defects.

### 7.6 Coverage-over-time trend *(coverage)*
Population % of key fields by `reconciled_published_date` month/quarter — are recent records
better annotated than older ones? **QA action:** decide whether to backfill old records.

### 7.7 Deprecation / migration tracker *(coverage)*
Residual `has_jurisdiction_tier_legacy` count (≈1,513 / 2.5%) and its trend — concrete backfill
progress against the ~2026-06-11 migration. **QA action:** track the migration to zero.

---

## 8. Honest coverage (shared between both apps)

- **One source of truth.** All population %, counts, and distributions come from `metrics.py`.
  The Gallery and the Cockpit render the *same* numbers; they cannot disagree.
- **Real, not aspirational.** Coverage % are computed from the snapshot after the empties→NA pass
  (a present-but-empty field is *missing*). The apps never display 100% unless it is real.
- **Sparsity is shown, not hidden.** The drill-down hides empty sections; the coverage matrix
  shows red where data is thin; nothing is padded to look complete.
- **Scope is labelled.** The sampling-caveat banner (60K contiguous slice, 403/1,087 topics, not
  random) appears on both apps; corpus-wide breadth ("1,087 topics, 241 jurisdictions") is clearly
  marked as describing the full dataset vs. the slice's live metrics.

---

## 9. Cross-cutting decisions

### 9.1 Performance
- **Snapshot, not live.** Apps read the local JSONL/parquet; **no live API on render** (hard
  constraint).
- **Build once.** `normalize_frame` writes `annotations.parquet` on first run; thereafter the
  parquet loads directly.
- **Cache aggressively.** `load_normalized` is wrapped in `st.cache_data` (frame cached once per
  session); `metrics`/`richness`/`quality` results are cached keyed by the `FilterState`
  signature so re-filtering is fast.
- **Targets (feel).** Cold first load (build parquet) within a few seconds; warm load near-instant;
  filter re-render in roughly sub-second over the 60K rows. (Exact numbers verified in Stage 02.)

### 9.2 Honest-coverage stance
Per §8 — real %s, shared metrics module, sampling banner, empty sections hidden.

### 9.3 Testability (what gets unit-tested; HTTP stubbed)
- `normalize`: empties/placeholders→NA; presence flags; counts (incl. `n_actionable_lanes` over
  the 7 lanes); nested-path mapping; date parsing + `*_calendar` pairing.
- `metrics`: `coverage` math on a tiny crafted frame; distribution bucketing; breadth counts;
  volume-over-time grouping.
- `richness`: score bounded `[0,100]`; monotonic as components gain population; highlight-reel
  determinism (stable order, diversity pass).
- `quality`: each predicate fires true/false on crafted rows; each anomaly rule fires on a record
  engineered to violate it (out-of-range score, mismatched label, reversed dates, 2105 pub date,
  duplicate entry_id, bad country, residual tier, rare update_type, near-dup regulator).
- `ingest.pull_snapshot`: pagination/termination logic with **httpx stubbed** (no network).
- `filters.apply_filters`: each filter narrows the frame correctly; composition is conjunctive.

### 9.4 Repo conventions
- **Python 3.12**, `.venv/` virtual environment.
- **Dependencies:** `httpx` + `python-dotenv` (one-time pull), `pandas` + `pyarrow`
  (normalize/persist), `streamlit` + a charting lib for the apps, `pytest` for tests. **Charting
  candidate: Plotly** (interactive, integrates cleanly with Streamlit); final pick is a Stage-02
  detail.
- **Secrets:** `CARVER_API_KEY` in a **git-ignored `.env`**; never committed; only the one-time
  puller reads it.
- **Layout** (illustrative — §11):

```
carver-data-showcase/
├─ carver_showcase/          # shared pipeline package
│  ├─ config.py  ingest.py  schema.py  normalize.py  load.py
│  ├─ metrics.py  richness.py  quality.py
├─ apps/
│  ├─ gallery.py             # (A) external
│  ├─ cockpit.py             # (B) internal
│  └─ components/  filters.py  render.py
├─ data/                     # git-ignored: annotations.jsonl, annotations.parquet, topic_categories.csv
├─ tools/  coverage_probe.py
├─ tests/
├─ docs/  README.md  LESSONS.md  v2-llm-enrichment-ideas.md
├─ .env                      # git-ignored: CARVER_API_KEY
├─ requirements.txt
└─ README.md
```

---

## 10. v2 / LLM-deferred ideas (captured in `docs/v2-llm-enrichment-ideas.md`, not built)

Each is an enhancement that would need an LLM and is therefore explicitly out of v1, so the value
isn't lost and the no-LLM line stays clean:

1. **Semantic search** over annotations (embeddings) — v1 has structured filters only.
2. **Natural-language quality critique** — an LLM explaining *why* a record is weak — v1 uses
   deterministic predicates.
3. **Auto-summarized gap explanations** in the Cockpit — v1 shows counts + rule names.
4. **Regulator-name canonicalization via embeddings / fuzzy matching** — v1 uses deterministic
   string canonicalization only.
5. **`update_type` taxonomy consolidation** by semantic clustering — v1 flags sprawl + rare values
   deterministically.
6. **Topic → category auto-classification** (removes the A3 sidecar dependency) — v1 uses
   field/sidecar/`"Uncategorized"`.
7. **Semantic duplicate detection** beyond exact `entry_id` match — v1 flags exact dupes only.
8. **"Ask the corpus" Q&A** over the dataset — out of v1 entirely.

---

## 11. Explicit assumptions & open items

- **A1** score range `[0,10]`, confidence `[0,1]` (§2.1) — inferred from payload; drives
  `score_out_of_range`.
- **A2** label bands `low[0,4)/medium[4,7)/high[7,10]` (§2.1) — a checking convention, not a
  data rewrite; drives `label_score_mismatch`.
- **A3** `category` source is field → sidecar → `"Uncategorized"`, and its population is measured,
  not assumed (§4.2).
- **Source fields** (`summary`, `language`) are extracted from `input_data.extracted_metadata.*`
  *when present*; their real population is reported by the coverage matrix rather than asserted —
  so the design never relies on a field the payload may lack.
- **No placeholders/TBDs in load-bearing sections.** The only deferred items are the four
  explicitly-Stage-02 ones (build order, file list, exact function bodies, final chart pick), which
  this stage is required to defer.

### 11.1 Self-consistency check (criterion 14)
- The schema (§4) names only fields confirmed in the verified payload (§2.1) or resolved by an
  explicit assumption (category, A3). No view references a column the schema doesn't define.
- Coverage numbers used to size the design (§2.3) match the rules that consume them (§5.3, §7) and
  are framed as *computed at load*, not hard-coded into the UI.
- `metrics` is the single coverage source for both apps (§3.1, §8), satisfying the
  "no duplicated logic" and "shared coverage story" constraints.
- Every derived signal in §5 is a formula/threshold with no model call, satisfying the no-LLM
  constraint; each LLM-tempting spot is named and routed to §10.

This spec decides the modules, the normalized schema, each app's view inventory, and the
deterministic formulas/predicates/rules in enough detail that Stage 02 can produce the phased build
plan and file-by-file list without re-deciding any of the design.
