# Themes & Entities — Stage 02 Phased Implementation Plan

**Implements:** the approved spec at `stages/01-spec/artifact.md` (the single source of
design truth) and the brief in `goal.md`. **No design is re-decided here** — every step
cites the spec section it builds. This is the build sequence + per-file / per-test change
list a subagent-driven-development loop can execute top-to-bottom.

## How to read this plan
- **Phases run in order; steps within a phase run in order.** Each step builds only on
  already-green prior steps — no forward dependencies (rubric 2).
- **Every code step is test-driven (rubric 3):** write the named **test(s) FIRST** (with the
  specific cases), watch them fail, then write the implementation to make them pass.
- **Acceptance** gives the exact command and what "green" means (rubric 6). Commands assume
  the repo root and the project venv (`.venv/bin/python`), matching the existing tooling.
- **No test hits the network or OpenAI** — every OpenAI-touching test uses a **stubbed
  client** (rubric 4). The single live step is **Phase 9**, isolated and flagged.
- **Constraints encoded throughout (rubric 9):** `OPENAI_API_KEY` is imported **only** in
  `tools/classify_entities.py`; `carver_showcase/*` and `apps/*` never import `openai`; the
  **Data-Quality Cockpit is never touched**; categories stay internal; **nothing is
  committed**; subagent dispatch is right-sized; **python-code-reviewer runs after each code
  change** (Python Expert fixes findings), per `CLAUDE.md`.

## Conventions used by every step
- **Run a test:** `.venv/bin/python -m pytest <path> -q`.
- **Run all tests:** `.venv/bin/python -m pytest -q`.
- **Review gate (per `CLAUDE.md`):** after a step's code is green, run **python-code-reviewer**
  on the new/changed files; the **python-expert** fixes any findings before the next step.
  This gate is implicit on every code step and called out explicitly in Phase 10.

## Test inventory (matches spec §8.2; rubric 12)
| Test file | Status | Covers |
|---|---|---|
| `tests/test_extract_terms.py` | **new** | counting, per-occurrence `count`, trim/empty-drop, missing/non-list skip, deterministic order |
| `tests/test_classify_entities.py` | **new** | request-builder, parser, detect→retry→fallback, resume-or-submit sidecar, incremental cache, `--sample` — all stubbed |
| `tests/test_build_term_stats.py` | **new** | breakdown, alias merge + `_clean_canonical`, breakdown-unchanged-by-merge, leaderboards, meta |
| `tests/test_load_term_stats.py` | **new** | `load_term_stats()` returns dict vs `None` (graceful) |
| `tests/test_charts.py` | **edit** | + 3 builders (happy + `_empty_fig`) |
| `tests/test_gallery_smoke.py` | **edit** | + tab present/renders with artifacts; gracefully absent without |
| `tests/test_deck.py` | **edit** | + active-slide page count (with/without term stats) |

---

# Phase 0 — Foundation: dependency + config constants
*Spec §7 (touch-points), §4.1 (taxonomy), §4.4 (batch paths). No design; logic-free constants.*

### Step 0.1 — Add `openai` to requirements and install
- **Test-first:** none (dependency change). Sanity only.
- **Implementation:**
  - Edit `requirements.txt`: add `openai` pinned per the repo's fully-pinned convention
    (choose the current latest at install time; pin the exact version in the file).
  - Install into the existing venv: `.venv/bin/python -m pip install -r requirements.txt`.
- **Files touched:** `requirements.txt`.
- **Acceptance:** `.venv/bin/python -c "import openai; print(openai.__version__)"` prints a
  version; `.venv/bin/python -m pytest -q` is still green (no regressions).
- **Traceability:** spec §7 (`requirements.txt += openai`), §8.1 (secrets-only-in-tools — the
  import lands only in the classify tool later).

### Step 0.2 — Add config constants (paths, taxonomy, model/chunk/top-N)
- **Test-first:** `tests/test_config_term_stats.py` (**new**, light import test):
  - `ENTITY_TYPES` is a 6-tuple **exactly** `("Regulator / Supervisor", "Government body",
    "International body", "Company", "Person", "Other")` (order + spelling, spec §4.1).
  - `ENTITY_TYPE_DEFINITIONS` has a key for **every** bucket; `ENTITY_TYPE_COLORS` has a hex
    colour for **every** bucket (keys == `ENTITY_TYPES`).
  - All new path constants are `pathlib.Path` under `DATA_DIR`.
  - `ENTITY_CHUNK_SIZE == 50`, `OPENAI_MODEL == "gpt-4o-mini"`, `MAX_RETRIES` is a small int,
    `ENTITY_LEADERBOARD_TOP_N == 20`, `TAG_LEADERBOARD_TOP_N == 20`.
- **Implementation:** edit `carver_showcase/config.py` (logic-free, matching its existing
  style) to add:
  - **Paths:** `ENTITY_MENTIONS_CSV`, `TAG_MENTIONS_CSV`, `ENTITY_TYPES_CSV`,
    `ENTITY_TYPE_BREAKDOWN_CSV`, `ENTITY_LEADERBOARD_CSV`, `TAG_LEADERBOARD_CSV`,
    `TERM_STATS_META_JSON`, `ENTITY_BATCH_REQUESTS_JSONL`, `ENTITY_BATCH_OUTPUT_JSONL`,
    `ENTITY_BATCH_STATE_JSON` (all `DATA_DIR / "<name>"`).
  - **Taxonomy:** `ENTITY_TYPES` (ordered tuple), `ENTITY_TYPE_DEFINITIONS` (bucket→def),
    `ENTITY_TYPE_COLORS` (bucket→hex).
  - **Enrichment:** `OPENAI_MODEL = "gpt-4o-mini"`, `ENTITY_CHUNK_SIZE = 50`,
    `MAX_RETRIES = 2`, `ENTITY_LEADERBOARD_TOP_N = 20`, `TAG_LEADERBOARD_TOP_N = 20`.
- **Files touched:** `carver_showcase/config.py`, `tests/test_config_term_stats.py` (new).
- **Acceptance:** `.venv/bin/python -m pytest tests/test_config_term_stats.py -q` → green.
- **Traceability:** spec §7 (config additions), §4.1 (taxonomy), §4.4 (`ENTITY_CHUNK_SIZE`,
  batch paths, sidecar), §5.1 (`ENTITY_TYPE_COLORS`), §5.2 (top-N).

---

# Phase 1 — `tools/extract_terms.py` (deterministic mention counting)
*Spec §2.1, §3.1–3.2. No key, no LLM.*

### Step 1.1 — Tests for extract_terms (write FIRST)
- **Test-first:** `tests/test_extract_terms.py` (**new**) — drive a small **factored**
  counting function (e.g. `count_terms(records) -> (entity_counter, tag_counter)` and an
  ordering/writer helper) over in-memory dicts / a tiny temp JSONL, **no real data file**:
  - **Per-occurrence `count` (§3.1, rubric 7d):** a record whose `entities` list contains the
    same string twice contributes **2** to that entity's count (Counter over list items).
  - **Whitespace-trim / empty-drop (§2.1):** `"  EBA  "` counts as `"EBA"`; `""`/whitespace-only
    items are dropped.
  - **Missing / non-list fields skipped (§2.1):** records with no `output_data.metadata`, or
    `tags`/`entities` absent / `None` / a non-list, are skipped without raising.
  - **Deterministic output order (§3.1 tie-break, rubric 7e):** the written rows are ordered
    `count` **desc, then term asc**; assert that two equal-count terms come out in ascending
    lexical order (this ordering is load-bearing for reproducible chunking).
- **Acceptance:** the test file exists and **fails** (no implementation yet).

### Step 1.2 — Implement extract_terms
- **Implementation:** `tools/extract_terms.py` (**new**) — stream `ANNOTATIONS_JSONL` once via
  `carver_showcase.ingest.load_snapshot` (the existing generator; memory-bounded), accumulate
  two `collections.Counter`s over `output_data.metadata.{entities,tags}` (per-occurrence,
  trimmed, empties dropped), and write `ENTITY_MENTIONS_CSV` / `TAG_MENTIONS_CSV` sorted
  `count` desc then term asc. Runnable as `.venv/bin/python tools/extract_terms.py`. **No
  OpenAI import.**
- **Files touched:** `tools/extract_terms.py`.
- **Acceptance:** `.venv/bin/python -m pytest tests/test_extract_terms.py -q` → green.
  python-code-reviewer clean on the new file.
- **Traceability:** spec §2.1, §3.1, §3.2.

---

# Phase 2 — `tools/classify_entities.py` (OpenAI Batch; STUBBED in tests)
*Spec §4.2–4.6. The largest unit — split into sub-steps (rubric 11). Every test uses a
**stubbed client; no network** (rubric 4). This is the **only** module that imports `openai`
and reads `OPENAI_API_KEY` (spec §8.1, rubric 9).*

> All sub-steps share one new test file `tests/test_classify_entities.py` and inject a fake
> client (a small stub object with the methods the tool calls), so no live API is ever hit.

### Step 2.1 — Request-builder + deterministic chunking (tests FIRST)
- **Test-first** (`tests/test_classify_entities.py`):
  - **Deterministic ~50-chunking (§4.4, rubric 7e):** given the on-disk `entity_mentions.csv`
    order, chunking into `ENTITY_CHUNK_SIZE` groups is reproducible from the file alone; the
    last chunk holds the remainder; `custom_id == f"chunk-{i:05d}"`.
  - **Request body shape (§4.2):** each request line has `method:"POST"`,
    `url:"/v1/chat/completions"`, `body.model == OPENAI_MODEL`, `temperature == 0`, the
    **taxonomy present** in the system/instruction message, and the chunk's entities in the
    user payload.
- **Implementation:** the request-builder function (pure: distinct-entity list → list of
  request-line dicts; writes `ENTITY_BATCH_REQUESTS_JSONL`). No client needed.
- **Acceptance:** `pytest tests/test_classify_entities.py -q -k request_builder` green.
- **Traceability:** §4.2, §4.4.

### Step 2.2 — Response parser + schema validation (tests FIRST)
- **Test-first:** parser maps each output line's `custom_id` → that chunk's entities and
  returns `{entity,type,canonical_name}` rows; a well-formed `type="Other"` row (an
  unidentifiable entity, §4.2) is **valid** and not flagged; an unknown `type` not in
  `ENTITY_TYPES`, a missing field, or non-JSON is flagged per §4.3.
- **Implementation:** the parser/validator (pure functions over decoded output lines).
- **Acceptance:** `pytest ... -k parser` green.
- **Traceability:** §4.2, §4.3.

### Step 2.3 — detect → retry → fallback (tests FIRST; rubric 7b)
- **Test-first (stubbed client):**
  - **Detect:** a short response (fewer objects than entities sent) and a malformed response
    are both detected as needing reclassification.
  - **Retry (bounded):** a stub that returns malformed once then valid → the offending
    entities are **retried via the sync `--sample` path** and resolved; assert the retry was
    attempted (call count) and the final rows are correct.
  - **Fallback after `MAX_RETRIES`:** a stub that stays malformed through `MAX_RETRIES` →
    unresolved entities become `type="Other", canonical_name=entity`, and the fallback **count
    is logged** (assert via caplog or a returned summary).
- **Implementation:** the detect→retry→fallback controller calling the sync path for retries.
- **Acceptance:** `pytest ... -k retry` green.
- **Traceability:** §4.3, §8.2.

### Step 2.4 — Resume-or-submit sidecar + incremental cache (tests FIRST; rubric 7a)
- **Test-first (stubbed client + tmp_path):**
  - **Submit-fresh:** no `entity_batch_state.json` → the tool uploads, creates ONE batch, and
    **writes the sidecar** with `batch_id` + `input_sha256` + `input_row_count` before polling.
  - **Resume:** a sidecar whose `input_sha256` **matches** the current input set → the tool
    **resumes** (polls/fetches that `batch_id`) and does **not** submit a new job (assert no
    `create` call).
  - **Hash-mismatch resubmit:** a sidecar whose hash **differs** from the current input set →
    submit fresh.
  - **Clear semantics:** sidecar cleared only **after** output fetched + merged into
    `entity_types.csv`; a terminal `failed`/`expired` status clears the sidecar (allowing a
    resubmit next run).
  - **Incremental cache (§4.5):** entities already present in `entity_types.csv` are excluded
    from the input set (set-difference on `entity`); an already-complete cache → **no** batch
    submitted.
- **Implementation:** the sidecar read/write/clear + resume-or-submit orchestration + cache
  set-difference; merge new rows into `ENTITY_TYPES_CSV`.
- **Acceptance:** `pytest ... -k "sidecar or cache"` green.
- **Traceability:** §4.4, §4.5.

### Step 2.5 — `--sample N` sync path + CLI wiring (tests FIRST)
- **Test-first (stubbed client):** `--sample N` classifies N entities via the **synchronous**
  Chat Completions path (no Files upload / no batch / no polling), prints results, and does
  **not** write the full cache; it shares the parser/validator from 2.2.
- **Implementation:** argparse CLI (`--sample N` default off), `load_dotenv(ROOT/.env)` +
  `os.environ["OPENAI_API_KEY"]` read **only here**, client construction behind a seam that
  tests replace with the stub. Full run (no `--sample`) wires 2.1→2.4.
- **Files touched:** `tools/classify_entities.py` (new), `tests/test_classify_entities.py` (new).
- **Acceptance:** `.venv/bin/python -m pytest tests/test_classify_entities.py -q` → all green;
  `.venv/bin/python tools/classify_entities.py --help` shows `--sample`. python-code-reviewer
  clean. **Confirm** `grep -rn "import openai" carver_showcase apps` returns nothing.
- **Traceability:** §4.2, §4.4 (`--sample`), §8.1.

---

# Phase 3 — `tools/build_term_stats.py` (deterministic rollup)
*Spec §3.4–3.7, §4.5. No key, no LLM.*

### Step 3.1 — Tests for build_term_stats (write FIRST)
- **Test-first:** `tests/test_build_term_stats.py` (**new**), small in-memory frames:
  - **Breakdown (§3.4):** join `entity_mentions` × `entity_types`; group by `type` →
    `mentions = Σ count`, `distinct_entities = nunique(entity)`; **all 6 buckets present**,
    zero-filled if empty; entities missing from types default to `Other`.
  - **Alias merge + `_clean_canonical` (§4.5, rubric 7c):** `_clean_canonical` strips leading
    `"U.S. "`, collapses/trims whitespace, unifies punctuation, casefolds **for the key only**;
    `SEC` / `Securities and Exchange Commission` / `U.S. Securities and Exchange Commission`
    (with distinct counts) collapse into **one** leaderboard row with the summed `mentions`,
    the highest-mention member's `type`, and its `canonical_name` as the display name.
  - **Breakdown-unchanged-by-merge invariant (§4.5, rubric 7c):** the breakdown computed before
    vs after the alias merge is **identical** (merge affects only the leaderboard).
  - **Leaderboards:** entity + tag leaderboards sorted by mentions/count desc, top-50 stored.
  - **Meta (§3.7):** `term_stats_meta.json` has exactly `n_distinct_entities`,
    `n_entity_mentions`, `n_distinct_tags`, `n_tag_mentions`, `model`, `enriched_at`,
    `n_classified` with correct values.
- **Acceptance:** test file exists and **fails**.

### Step 3.2 — Implement build_term_stats
- **Implementation:** `tools/build_term_stats.py` (**new**) — read the two mention CSVs +
  `entity_types.csv`; produce `ENTITY_TYPE_BREAKDOWN_CSV`, `ENTITY_LEADERBOARD_CSV`,
  `TAG_LEADERBOARD_CSV`, `TERM_STATS_META_JSON`. Runnable standalone. No OpenAI import.
- **Files touched:** `tools/build_term_stats.py`.
- **Acceptance:** `.venv/bin/python -m pytest tests/test_build_term_stats.py -q` → green;
  python-code-reviewer clean.
- **Traceability:** §3.4–3.7, §4.5.

---

# Phase 4 — `carver_showcase/charts.py` (3 pure builders)
*Spec §5.1. Pure `df→go.Figure`, defensive, added to `__all__`.*

### Step 4.1 — Tests for the 3 builders (write FIRST; extend test_charts.py)
- **Test-first** (extend `tests/test_charts.py`, same conventions as existing builder tests):
  - `fig_entity_type_breakdown` on a small breakdown frame → `go.Figure` with ≥1 trace; hover
    references `distinct_entities`.
  - `fig_entity_leaderboard` on a small leaderboard frame → `go.Figure`, **coloured by `type`**
    (uses `ENTITY_TYPE_COLORS`); honours `n`.
  - `fig_tag_leaderboard` on a small tag frame → `go.Figure` with ≥1 trace; honours `n`.
  - **Defensive (`_empty_fig`):** each returns a valid empty figure (no raise) on
    `None`/empty/missing-column input.
- **Acceptance:** new cases fail (builders not yet defined).

### Step 4.2 — Implement the 3 builders
- **Implementation:** add `fig_entity_type_breakdown`, `fig_entity_leaderboard`,
  `fig_tag_leaderboard` to `carver_showcase/charts.py` (mirroring the existing horizontal-bar
  builders + `_empty_fig` guard); append all three to `__all__`.
- **Files touched:** `carver_showcase/charts.py`, `tests/test_charts.py`.
- **Acceptance:** `.venv/bin/python -m pytest tests/test_charts.py -q` → green;
  python-code-reviewer clean.
- **Traceability:** §5.1.

---

# Phase 5 — `carver_showcase/load.py` (`load_term_stats`, graceful)
*Spec §7. Framework-agnostic; returns dict or `None`.*

### Step 5.1 — Tests for load_term_stats (write FIRST)
- **Test-first:** `tests/test_load_term_stats.py` (**new**, `tmp_path`):
  - With the 3 rollup CSVs + `term_stats_meta.json` present → returns
    `{"breakdown": df, "entity_leaderboard": df, "tag_leaderboard": df, "meta": dict}`.
  - With the core artifacts **absent** → returns **`None`** (graceful; no raise) — backs the
    gallery/deck graceful-absence behaviour (rubric 7f).
  - Does **not** read `entity_types.csv` or the mention CSVs (tool-internal).
- **Acceptance:** test exists and fails.

### Step 5.2 — Implement load_term_stats
- **Implementation:** add `load_term_stats(...) -> dict | None` to `carver_showcase/load.py`,
  following `load_catalog`/`load_snapshot_meta` (no Streamlit import).
- **Files touched:** `carver_showcase/load.py`, `tests/test_load_term_stats.py` (new).
- **Acceptance:** `.venv/bin/python -m pytest tests/test_load_term_stats.py -q` → green;
  python-code-reviewer clean.
- **Traceability:** §7, §3.8.

---

# Phase 6 — `apps/gallery.py` (conditional 9th tab)
*Spec §5.2–5.3, §6. Reads `df_full` (not `view`); hidden when artifacts absent.*

### Step 6.1 — Smoke tests for the tab (write FIRST; extend test_gallery_smoke.py)
- **Test-first** (extend `tests/test_gallery_smoke.py`, AppTest harness):
  - **Graceful absence (rubric 7f):** the app boots without exception when term-stats
    artifacts are absent, and the "Themes & Entities" tab is **not** present (the original 8
    tabs still render).
  - **Present + renders:** with artifacts available (monkeypatch the cached
    `load_term_stats` to return a small fixture dict), the app boots without exception and the
    "Themes & Entities" tab label is present.
  - **Categories stay internal:** the existing "no Category filter" assertion still holds.
- **Acceptance:** new cases fail (tab not yet added).

### Step 6.2 — Implement the tab
- **Implementation:** in `apps/gallery.py`:
  - Add a `@st.cache_data` wrapper `_load_term_stats()` calling `load.load_term_stats()`.
  - **Conditionally append** `"Themes & Entities"` to `TABS` only when `_load_term_stats()`
    is not `None` (existing `tabs[0]`…`tabs[7]` indices unchanged).
  - Tab body: header + **"across the full corpus — not affected by the sidebar filters"**
    caption (§6); the **headline tiles incl. Entity/Tag coverage %** (rubric 7h) — coverage and
    medians **derived live from `df_full`** (`(n_entities>0).mean()`, `(n_tags>0).mean()`,
    `median(...)`), distinct counts/totals from `meta`; the **three charts** (breakdown, entity
    leaderboard, tag leaderboard); the best-effort alias caveat note (§4.5).
- **Files touched:** `apps/gallery.py`, `tests/test_gallery_smoke.py`.
- **Acceptance:** `.venv/bin/python -m pytest tests/test_gallery_smoke.py -q` → green;
  python-code-reviewer clean. (Cockpit untouched — `apps/cockpit.py` unchanged.)
- **Traceability:** §5.2, §5.3, §6.

---

# Phase 7 — `carver_showcase/deck.py` (two-chart slide, 8→9)
*Spec §5.4. Two charts (breakdown + leaderboard) + tag KPI/callout; runtime active-slide list.*

### Step 7.1 — Deck tests (write FIRST; extend test_deck.py)
- **Test-first** (extend `tests/test_deck.py`, kaleido stubbed as today):
  - **With term stats present** (inject a small fixture): the deck builds and the page count is
    the **active-slide count including** the themes slide (i.e. 9).
  - **Without term stats** (rubric 7f): the deck builds with the original **8** slides, no
    themes slide, no exception.
  - The page-count assertion is updated from a fixed `len(SLIDES)` to the **active slide list**.
- **Acceptance:** new cases fail (slide + compose not yet added).

### Step 7.2 — Implement the slide + active-slide compose
- **Implementation:** in `carver_showcase/deck.py`:
  - Add `_slide_themes_entities(c, ctx, df, catalog_df)` — the **two-chart** curated slide
    (rubric 7g): a KPI row (Distinct entities · Distinct tags · Entity coverage · Tag coverage ·
    Median entities/rec), **two half-width charts** (`fig_entity_type_breakdown` left,
    `fig_entity_leaderboard` top-12 right), and a full-width callout (top themes line + alias
    caveat) — per the §5.4 layout, reusing the shared builders so it can't drift from the
    gallery.
  - Extend `_build_context` to carry term-stat numbers (distinct counts, totals, medians,
    coverage %, top buckets, top themes) — loaded via `load_term_stats()` inside `build_deck`.
  - In `build_deck`, **compose the active slide list at runtime**: include the themes slide
    only when `load_term_stats()` returns data (else the original 8).
- **Files touched:** `carver_showcase/deck.py`, `tests/test_deck.py`.
- **Acceptance:** `.venv/bin/python -m pytest tests/test_deck.py -q` → green;
  python-code-reviewer clean.
- **Traceability:** §5.4.

---

# Phase 8 — Full unit-test green gate (no network)
*Everything above is verifiable with **zero** OpenAI calls and **no real artifacts**.*

### Step 8.1 — Whole-suite green + isolation checks
- **Acceptance:**
  - `.venv/bin/python -m pytest -q` → **all green** (new + existing).
  - `grep -rn "import openai" carver_showcase apps` → **no matches** (secrets/SDK only in the
    tool; rubric 9).
  - `git status` shows only the expected new/edited files; **nothing committed**.
- **Traceability:** §8.1, §8.2.

---

# Phase 9 — Operational enrichment run (the ONE live step) ⚠️
*The only step that hits the network and spends money. Sequenced **after** all unit tests are
green; no green test depends on it (rubric 8). Requires `OPENAI_API_KEY` in the git-ignored
`.env`.*

### Step 9.1 — Extract mentions (offline, no key)
- **Run:** `.venv/bin/python tools/extract_terms.py`.
- **Acceptance:** `data/entity_mentions.csv` (~281K rows) and `data/tag_mentions.csv` (~234K
  rows) exist, ordered `count` desc then term asc; counts plausibly match the brief
  (~900K entity / ~1.54M tag mentions).

### Step 9.2 — Dry-run the prompt with `--sample` (small spend)
- **Run:** `.venv/bin/python tools/classify_entities.py --sample 100`.
- **Acceptance:** ~100 entities classified into the 6 buckets with sensible `canonical_name`s;
  iterate the prompt copy here until the sample looks right. (Sync path; no batch submitted.)

### Step 9.3 — Full Batch classify (~$1, async; resumable) ⚠️
- **Run:** `.venv/bin/python tools/classify_entities.py` — builds ~5,624 request lines, submits
  **ONE** Batch job (`gpt-4o-mini`), writes `data/entity_batch_state.json`, polls, fetches,
  merges into `data/entity_types.csv`, clears the sidecar. If interrupted, **re-run the same
  command** — it resumes the in-flight job (no duplicate submit, §4.4).
- **Acceptance:** `data/entity_types.csv` covers all distinct entities; every `type` ∈
  `ENTITY_TYPES`; the sidecar is cleared on success.

### Step 9.4 — Build rollups (offline, no key)
- **Run:** `.venv/bin/python tools/build_term_stats.py`.
- **Acceptance:** `data/entity_type_breakdown.csv` (6 rows), `data/entity_leaderboard.csv`,
  `data/tag_leaderboard.csv`, `data/term_stats_meta.json` exist with the §3 schemas.
- **Traceability:** §2 (data flow), §4.4, §4.6 (~$1 envelope).

---

# Phase 10 — Final verification & review
*Closing gate (rubric 10). Acceptance is concrete; nothing is committed.*

### Step 10.1 — Full suite + code review
- **Run:** `.venv/bin/python -m pytest -q`; then **python-code-reviewer** on **all** new/changed
  Python (`tools/extract_terms.py`, `tools/classify_entities.py`, `tools/build_term_stats.py`,
  `carver_showcase/{config,charts,load,deck}.py`, `apps/gallery.py`, the new/edited tests);
  **python-expert** fixes findings; re-run pytest to green.
- **Acceptance:** all tests green; reviewer reports no outstanding findings.

### Step 10.2 — Live gallery shows the tab
- **Run:** `.venv/bin/streamlit run apps/gallery.py` (`:8501`).
- **Acceptance:** the **"Themes & Entities"** tab appears (9th), renders the coverage/median
  tiles + the 3 charts + the "across the full corpus" caption, and does **not** react to the
  sidebar filters (§6). No Category filter anywhere (categories internal).

### Step 10.3 — Deck rebuilds to 9 slides
- **Run:** `.venv/bin/python tools/build_deck.py`.
- **Acceptance:** the regenerated `data/carver-state-of-data.pdf` has **9** slides incl. the
  two-chart Themes & Entities slide; the gallery's deck-download serves it.

### Step 10.4 — Cockpit unchanged + nothing committed
- **Run:** `.venv/bin/streamlit run apps/cockpit.py` (`:8502`); `git status`; `git diff --stat`.
- **Acceptance:** the Data-Quality Cockpit behaves exactly as before (`apps/cockpit.py` shows
  **no diff**); `git status` shows only the intended new/edited files; **nothing is committed**
  (the user merges via their own flux workflow).
- **Traceability:** §8.1 (constraints), `goal.md` (no-commit, cockpit untouched, categories
  internal).

---

## Traceability summary (rubric 1 + 7)
| Hard spec behaviour | Built in | Tested in |
|---|---|---|
| (a) resume-or-submit sidecar + hash-mismatch resubmit (§4.4) | 2.4 | 2.4 |
| (b) detect→retry→fallback, `Other` after `MAX_RETRIES` (§4.3) | 2.3 | 2.3 |
| (c) alias merge + `_clean_canonical`; breakdown-unchanged-by-merge (§4.5) | 3.2 | 3.1 |
| (d) per-occurrence `count` (§3.1) | 1.2 | 1.1 |
| (e) deterministic chunking order (§3.1 tie-break) | 1.2 / 2.1 | 1.1 / 2.1 |
| (f) graceful absence — gallery hides tab / deck 8-slide compose (§5.3–5.4, §7) | 5.2 / 6.2 / 7.2 | 5.1 / 6.1 / 7.1 |
| (g) two-chart deck slide composition (§5.4) | 7.2 | 7.1 |
| (h) coverage tiles (§5.2) | 6.2 | 6.1 |

## Out of scope (this stage)
- Re-deciding any design (taxonomy, schemas, batch mechanics, chart/slide content) — all
  settled in the approved spec; this plan only cites it.
- The actual implementation code (that is execution, after this plan is approved).
- Re-pulling data; any Cockpit or category change.
