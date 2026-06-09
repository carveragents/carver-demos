# Stress-test 003 — stage 02-plan (orchestrator read-through)

Grounded check that the approved plan (`stages/02-plan/artifact.md`) is executable as the terminal
build plan. Answered from the plan + the approved spec.

**Q1. Can a fresh implementer build each spec §3.1 module from the plan alone?** Yes — Phases 1–7
map every module (config/schema, ingest/normalize, load/metrics, richness/quality, filters/render,
gallery, cockpit) with files, spec-referenced interfaces, tests-first, and a verification command. ✔

**Q2. Are all Gallery (§6) + Cockpit (§7) views covered, incl. the G4/G5 additions?** Yes — Phase 6
table maps v0–v9 incl. v1a (institutions, G4) and the historical-depth block (G5); Phase 7 maps
7.1–7.7. ✔

**Q3. Is the no-LLM + direct-API + honest-coverage constraint preserved?** Yes — section G(8): all
signals are the spec §5 formulas; only the sanctioned catalog GET + the existing snapshot; apps read
local parquet/CSV; tests stub httpx. ✔

**Q4. Does it avoid re-pulling existing data?** Yes — section A marks `annotations.jsonl`,
`topic_categories.csv`, and the pullers DONE; only `topic_catalog.csv` is scheduled (Phase 0). ✔

**Q5. (GROUNDED) The spec §4.2 prose puts `title`/`feed_url` under
`input_data.extracted_metadata`, but the real payload has them under
`output_data.classification.metadata`. Does the plan get this right?** Yes — Risk R2 + the Phase-1
`FIELD_MAP` pin the **probe-confirmed** paths (title 95.6%, feed_url 53.9%) and `test_normalize.py`
asserts the resulting population, so a wrong path fails fast. This is the correct "trust the live
payload" call (per `docs/data-model.md`). ✔

**Q6. Are the known data hazards handled?** Yes — R1 parquet build over 423 MB (stream + drop raw
payload), R3 ISO mapping for choropleth, R6 Streamlit perf (precompute + cache), R7 Python 3.12,
R8 cross-row anomalies on the full frame. ✔

## Verdict
No gaps. The plan is executable phase-by-phase from plan + spec alone. Nothing left to add →
`--finish` (pipeline COMPLETE).
