# Public deployment — implementation plan

Spec: `docs/superpowers/specs/2026-06-12-public-deployment-design.md`.
Execution: subagent-driven TDD; spec-compliance + code-quality review per task.
Standing constraints: never `git commit`/`add` during dev; gallery+deck only (the
Cockpit + shared cockpit components untouched except where a flag is threaded
backward-compatibly); `OPENAI_API_KEY`/`CARVER_API_KEY` only in `tools/`; restart
Streamlit after editing imported modules; don't run the deck build concurrently
with the test suite (AppTest flake).

## Task 1 — Config foundation (`carver_showcase/config.py`)
- `import os`; `DATA_DIR = Path(os.environ.get("CARVER_DATA_DIR") or <repo>/data)`
  (all existing path constants derive from DATA_DIR — verify they still do).
- Add: `PUBLIC_DATA_SUBDIR = "public"`; `PUBLIC_KEEP_COLUMNS` (the 16, ordered);
  `PUBLIC_CONTENT_DENYLIST` (frozenset of forbidden substrings/names: title, summary,
  feed_url, base_url, reasoning, regulator_name, regulator_division,
  regulator_other_agency, artifact_id, entry_id, source_id); `PUBLIC_STRING_MAXLEN = 64`;
  `PUBLIC_ROWCOUNT_DROP_TOLERANCE = 0.20`; `UPSTREAM_RECORD_TOLERANCE = 0.01`.
- Keep config logic-free (constants + the one env read only).
- **Tests** (`tests/test_config_public.py`): `CARVER_DATA_DIR` override changes DATA_DIR
  and a derived path (use monkeypatch + importlib.reload); KEEP set has no duplicates and
  is ⊆ `schema.NORMALIZED_COLUMNS`; KEEP ∩ DENYLIST == ∅.

## Task 2 — Loader allowlist (`carver_showcase/load.py`)
- `load_normalized(..., keep_columns: list[str] | None = None)`: after reading the
  parquet, if `keep_columns` is given, return `df[[c for c in keep_columns if c in df.columns]]`
  (intersection, order preserved). Default None = unchanged behaviour.
- **Tests** (`tests/test_load_public.py`): with `keep_columns`, only those columns return,
  even if the parquet has extras; missing keep columns are skipped (no KeyError); None = full.

## Task 3 — Gallery public build (`apps/gallery.py`)
- `PUBLIC_BUILD = os.environ.get("CARVER_PUBLIC_BUILD") == "1"` near the top.
- `_load_df`: when PUBLIC_BUILD, call `load_normalized(keep_columns=PUBLIC_KEEP_COLUMNS)`.
- TABS: when PUBLIC_BUILD, omit "Record Drill-Down" and "Highlight Reel".
- Wrap both tab bodies in `if not PUBLIC_BUILD:` and skip `_load_record_index()` /
  `build_record_index` / `get_raw_record` in public mode (no JSONL access).
- Verify `apply_filters` already skips absent columns (it guards `if col in df.columns`);
  add a regression test if not.
- **Tests** (`tests/test_gallery_smoke.py`): a `CARVER_PUBLIC_BUILD=1` AppTest variant —
  app boots; TABS excludes the two record tabs; no exception; (assert no JSONL read by
  pointing ANNOTATIONS_JSONL at a non-existent path via CARVER_DATA_DIR and a slim fixture).

## Task 4 — Export tool (`tools/export_public_bundle.py`)
- `build_public_bundle(src_data_dir, out_dir)`: load the normalized frame from
  `src_data_dir`, select `PUBLIC_KEEP_COLUMNS` (intersection, error if a KEEP col is
  missing), write `out_dir/annotations.parquet`; copy the aggregate sidecars
  (catalog, domains, the 4 term-stats files, snapshot_meta, deck PDF) into `out_dir`.
- Pure helper `slim_frame(df) -> df` + thin I/O wrapper; CLI `--src`, `--out`
  (default `data/`, `data/public/`).
- **Tests** (`tests/test_export_public_bundle.py`): `slim_frame` keeps exactly KEEP ∩ cols
  and drops a denylist column present in the input; row count preserved; sidecars copied;
  a missing KEEP column raises a clear error.

## Task 5 — Offline bundle validator (`tools/validate_bundle.py`)
- Pure check functions returning `(name, level, ok, detail)` where level ∈ {HARD, SOFT}:
  - leak: columns ⊆ KEEP; no denylist names; string `max(len) < PUBLIC_STRING_MAXLEN`.
  - completeness: rows > 0 and (no baseline OR drop ≤ tolerance); snapshot advanced;
    no KEEP col 100% null; KEEP schema present.
  - integrity: parquet + sidecars load non-empty; deck PDF readable + page count ≥ N;
    every topic_id ∈ catalog.
  - drift (SOFT): vs `baseline.json` — distinct counts, null-rates, score means,
    out-of-window date share, within relative tolerance.
- `run_validation(bundle_dir, baseline_path) -> report`; writes `validation_report.md`;
  updates `baseline.json` only when no HARD failed; `main()` exits 1 on any HARD FAIL.
- **Tests** (`tests/test_validate_bundle.py`): a clean fixture passes (exit 0); a bundle
  with a denylist/oversized-string column → HARD FAIL (exit 1); a collapsed row count vs
  baseline → HARD FAIL; drift only → WARN (exit 0); report + baseline written correctly.

## Task 6 — Upstream reconciliation (`tools/validate_upstream.py`)
- `make_client()`-style key read (only here + the other tools); **skip-clean if no key**.
- Checks: institutions↔topics (HARD, exact), curation invariant (HARD, local),
  records↔upstream-total (SOFT, tolerant — use a cheap count if available else the
  pull-stamped count), freshness (SOFT), referential (bonus).
- `run_upstream_checks(...)`; `main()` exits 1 on a HARD FAIL, 0 if skipped/clean.
- **Tests** (`tests/test_validate_upstream.py`): inject a fake API client — matching
  counts pass; a topic-count mismatch → HARD FAIL; a broken curation invariant → HARD
  FAIL; a small record drift → WARN; no key → skip-clean (exit 0). No live calls.

## Task 7 — Runtime requirements + deploy guide
- `requirements-public.txt`: streamlit, pandas, pyarrow, plotly, pycountry (+ kaleido/
  reportlab ONLY if the deck is rebuilt in-app — it isn't, so omit). No openai/httpx.
- `docs/DEPLOY.md`: Streamlit Community Cloud steps (repo, entrypoint, env vars, no
  secrets), the weekly loop, and the exact commit-gate command.
- **Tests:** none (docs/manifest); verify `requirements-public.txt` is import-sufficient
  for `apps/gallery.py` in public mode (a smoke import check).

## Final
Integration code-quality review across all new/changed files; full `pytest -q` green;
build a sample `data/public/` bundle locally and run both validators end-to-end to
prove the gate. Report the Streamlit Community Cloud setup needs back to the user.
