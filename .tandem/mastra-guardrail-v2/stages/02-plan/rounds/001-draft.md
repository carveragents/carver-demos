# Plan: Carver × Mastra Compliance Guardrail (v1)

**Stage:** 02-plan **Round:** 1 (initial draft)
**Status:** Draft
**Implements:** `stages/01-spec/artifact.md` (6,002 lines) — **verbatim**. This plan introduces
no design decisions. Where it looked like it needed one, that is a **spec issue** callout, not a
divergence. Section references (§N) are to the spec unless stated.

---

## 0. How to read this plan

**Task IDs are stable** (`P1.3`, `T6.2`) — dependency callouts and the parallelism map use them.
Every implementation task carries the same five fields, and none is optional:

| Field | Meaning |
|---|---|
| **Spec** | The section this task implements. If a task has no §, it is scaffolding. |
| **Creates** | Exact file paths and the exact function/class names, as spelled in the spec. |
| **Tests first** | The test file and the named cases to write **before** the implementation. |
| **Verify** | The literal command, and what output means "green". |
| **Also update** | **Every other place that states the same fact.** Non-negotiable — see below. |

### The "Also update" field exists because of one specific defect

The spec stage took 13 rounds, and the **single most recurring defect** — three times in the
spec alone, plus five more across its refinement cycles — was *fixing the authoritative site and
missing its restatements*: stale `{ compareWorkflow }` constructors surviving a registration fix;
§15's "Cost guarantees" still quoting a superseded call count; `isTripWireError` left owned by two
modules after its extraction. Each was individually trivial and collectively poisonous, because
**every fragment read correctly on its own.**

So: **a task that changes a figure, an owner, or an interface does not close until every
restatement of that fact is updated in the same task.** Where a fact is stated twice by
construction (a constant and its drift test; a fixture and both consumers), the task names both.
This is why several tasks below look over-specified in their "Also update" line — that line is the
one this project has proven it cannot leave to memory.

**A dependency claim must name a symbol.** The spec's final rounds established this rule and the
plan inherits it: when a task says module A depends on module B, it says *which symbol* — because
`(module)` alone is unfalsifiable, while `(module, symbol)` dies to a grep the moment it stops
being true.

---

## 1. The three sequencing facts, and what they buy

**Fact 1 — the real probe run is the only expensive, irreversible step.** Phases 0–6 make
**zero billed calls**. Everything is proven against stub clients and synthetic fixtures. The money
is spent **once**, in Phase 7, when every consumer of the data it produces is already green.

**Fact 2 — `template/` does not wait for real data.** It vendors `src/data/cleared-set.json`, but
every module can be built against a **synthetic fixture** conforming to the same
`ClearedRecordSchema`. So `template/` is built in Phase 6, *before* the real run. This is the
plan's most important ordering choice and it is worth being explicit about why: it means the
expensive step is paid against a **proven consumer**. If the template were built after the run and
turned out to need a schema change, the money would be spent twice. `schema.test.ts` (Zod-parsing
the vendored file) is what makes the eventual swap safe — it is the mechanism, not a hope.

**Fact 3 — two human checkpoints block, and neither can be automated.**
- **Human review** (§6) — the clearance gate. Manual, blocking, no batch-approve path exists in
  code or config, by design (§6's anti-padding row).
- **The <20-survivor escalation gate** (Phase 7, task `R7.5`) — a **hard stop** that reports to
  the user. It is the one condition the user asked to be woken for. It is a named step with its
  own ID, not a footnote.

---

## 2. Phase map, dependencies, and what can run in parallel

```
P0  scaffolding ──┬──────────────────────────────────────────────────────────┐
                  │                                                          │
                  ├─ P1  prep LEAF        (config reader extract candidates  │
                  │      + test_imports    urls sampling scenarios schema    │
                  │                        budget openai_client logging_)    │
                  │            │                                             │
                  │            ├─ P2  prep L1–L2 (probe judge scoring curate)│
                  │            │            │                                │
                  │            │            ├─ P3  prep L3 (scenario_decision│
                  │            │            │      generate_template_config) │
                  │            │            │            │                   │
                  │            │            │            ├─ P4 review.py     │
                  │            │            │            │      │            │
                  │            │            │            │      └─ P5 run_prep
                  │                                                          │
                  └─ P6  template/  (INDEPENDENT of P1–P5 — synthetic fixture)
                                                          │
                       P5 ∧ P6 ────────────────────────── ▼
                                        P7  THE REAL RUN  (money; human review; escalation gate)
                                                          │
                                        P8  vendor + generate template constants
                                                          │
                                        P9  verify the 9 success criteria
```

**Genuinely parallel tracks** (no shared state, no ordering between them):

| Track | Tasks | Why it is safe |
|---|---|---|
| **A — `prep/`** | P1 → P2 → P3 → P4 → P5 | Sequential *within* the track: the spec's module DAG (§1) is a strict `LEAF → L1 → L2 → L3 → L4`, so each level's dependents do not exist yet. |
| **B — `template/`** | P6 (all of it) | Touches no `prep/` file, imports nothing from it (goal #1), and consumes a **synthetic** fixture it creates itself. Can start the moment P0 lands. |
| **C — golden fixtures** | `P1.9` | Pure data. Both consumers (`test_scoring.py`, `scorers.test.ts`) are in different tracks; the fixture blocks neither until they assert it. |

**Within P1**, the ten LEAF modules are mutually independent (they import nothing from each
other — that is what makes them leaves) and can be built by parallel subagents. Same for the six
`prompts/*.md`. **Within P6**, the module DAG (§8) again dictates order:
`config/schema/firmProfile → judge/contract → judge/callJudge → agents → tools/processors → workflows → evals`.

**False parallelism to avoid** — these look independent and are not:
- P2's `curate.py` and P1's `budget.py`: `curate` imports `SpendBudget`. The whole point of
  `budget.py` being a leaf (§1) is that `probe`/`judge`/`curate` can all depend on it one-way; it
  must exist first.
- P6's `evals/scorers.ts` and `evals/deliveryWorkflow.ts`: scorers import the workflow's schemas.
- P8's two halves: the template constants are generated *from* the cleared set; vendoring must
  land first.

---

# PHASE 0 — Scaffolding

**Bills: nothing.** Ends green when `pytest` and `vitest` both run and collect zero tests without
import errors.

### P0.1 — Project skeleton and the two `.gitignore` facts
- **Spec:** §1 (layout), goal hard constraints
- **Creates:** `projects/mastra-guardrail/` with the §1 tree's directories;
  `projects/mastra-guardrail/.gitignore` covering **at minimum** `node_modules/`, `.mastra/`,
  `data/scratch/`, `prep/.venv/`, `.env`; `data/cleared/` **tracked** (it is the deliverable), with
  a `.gitkeep` so the empty dir survives.
- **Verify:** `git check-ignore -v prep/.venv data/scratch node_modules` names the project-local
  file for each; `git check-ignore data/cleared` exits non-zero (**not** ignored).
- **Also update:** root `README.md`'s Projects table (a row for this project) — goal's repo
  conventions require it and it is easiest to add now, while the layout is fresh.

### P0.2 — The venv, pinned, project-local
- **Spec:** goal #13
- **Creates:** `prep/.venv` via `python3.10 -m venv .venv` run **from `prep/`**;
  `prep/requirements.txt` (`openai==1.76.0`, `httpx==0.28.1`, `PyYAML`, `python-dotenv` — pinned,
  no ranges); `prep/requirements-dev.txt` (`pytest`, plus `pytest-cov` if the sibling uses it).
- **Verify:** `prep/.venv/bin/python -c "import openai, httpx, yaml, dotenv; print('ok')"` prints
  `ok`. `prep/.venv/bin/python -c "import carver_showcase"` **fails** with `ModuleNotFoundError` —
  goal #13's isolation, proven rather than assumed.
- **Note:** every documented Python command in this plan is `prep/.venv/bin/python …` run from
  `prep/`. No system Python, no sibling venv, ever.

### P0.3 — `config.yaml` and the `Settings` contract
- **Spec:** §13
- **Creates:** `prep/config.yaml` with **every** key §13's table lists, at its specified default:
  `model_router_string: openai/gpt-5.6-sol`, `annotations_path:
  ../../../../carver-showcase/data/annotations.jsonl` (**four** `../` — §13's I1 correction; three
  resolves inside this repo and fails on the first command), `candidate_cutoff_date: "2026-03-01"`,
  `sample_seed: 42`, `probe_batch_size: 40`, `target_set_size: 200`, `probe_max_records: 400`,
  `scenario_trial_size: 30`, `scenario_trial_min: 10`, `price_input_per_million_usd: 5.00`,
  `price_output_per_million_usd: 30.00`, `total_spend_ceiling_usd: 120.0`,
  `judge_confidence_floor: 0.7`, `dotenv_path: .env`, `cleared_dir: data/cleared`,
  `scratch_dir: data/scratch`.
- **Explicitly NOT keys** (§13, and each for a stated anti-padding reason): `reasoning_effort`,
  `snapshot_date`. Both are code constants. A task that adds either to `config.yaml` is wrong.
- **Creates:** `prep/.env.example` (`OPENAI_API_KEY=`), `template/.env.example` (same). Both
  tracked; both real `.env` files gitignored.
- **Verify:** file exists; `P1.1` asserts `load_settings()` reads it.

### P0.4 — `template/` build config (goal #12's locked stack)
- **Spec:** §8's `package.json`/`tsconfig.json` blocks
- **Creates:** `template/package.json` — `"type": "module"`, `"engines": {"node": ">=22.13.0"}`,
  scripts `dev`/`demo`/`demo:prompt`/`typecheck`/`test`/`test:unit` exactly as §8 pins them (note
  `test` runs `npm run typecheck && vitest run`); deps `@mastra/core@1.51.0`, `zod@4.0.0`,
  `dotenv@16.4.7`; devDeps `mastra@1.51.0`, `typescript@5.7.3`, `tsx@4.19.2`, `vitest@2.1.8`,
  `@types/node@22.13.0`. All exact pins, no carets. `template/tsconfig.json` — `module: ES2022`,
  `moduleResolution: bundler`, `resolveJsonModule: true`, `strict: true`, `noEmit: true`.
  `template/vitest.config.ts`.
- **Why this is Phase 0 and not later:** goal #12 names CommonJS as a *specific Mastra-breaking
  failure mode*. Getting `"type": "module"` and `moduleResolution: bundler` wrong is not a lint
  issue; it breaks resolution at the first import, and it is cheapest to get right before any
  module exists.
- **Verify:** `cd template && npm install && npm run typecheck` — passes on an empty `src/`.

### P0.5 — Work branch
- **Spec:** goal hard constraints
- **Do:** `git checkout -b feat-mastra-guardrail`. **Commit as you go. NEVER push.** No PR, no
  remote interaction of any kind — the user integrates via their own flux workflow.

---

# PHASE 1 — `prep/` LEAF modules

**Bills: nothing** (no module here takes a client). **Parallelizable:** all ten modules.
Ends green when `prep/.venv/bin/python -m pytest tests/ -q` passes and `test_imports.py` proves
the DAG.

### P1.0 — `test_imports.py` FIRST (the cheap guard on the whole build)
- **Spec:** §1's DAG + §14
- **Tests first (this task IS the test):** `test_no_circular_imports` — walk every `mastra_prep`
  module with `ast`, extract intra-package imports **without executing them**, assert the graph is
  acyclic and that `budget.py`'s and `logging_.py`'s intra-package import sets are **empty**;
  `test_never_imports_carver_showcase` — the same walk asserts no module imports `carver_showcase`
  (goal #13); `test_no_stdlib_shadowing` — no module named `logging`/`json`/`types` (this is why
  `logging_.py` carries its underscore).
- **Why first:** it is ~30 lines, needs no implementation to exist, and it is the mechanical guard
  against the exact defect the spec stage found in the wild (`probe → curate → probe`). It costs
  nothing and it fails the instant someone reintroduces a cycle.
- **Verify:** `prep/.venv/bin/python -m pytest tests/test_imports.py -q` — passes trivially on an
  empty package, and keeps passing as P1–P5 land.

### P1.1 — `config.py`
- **Spec:** §13 | **Creates:** `mastra_prep/config.py` — `Settings` (dataclass),
  `load_settings(path="config.yaml") → Settings`
- **Tests first:** `test_config.py` — `load_settings()` raises `ValueError` for
  `judge_confidence_floor: 0.5` (below the 0.7 floor); for `price_input_per_million_usd` /
  `price_output_per_million_usd` below `PINNED_PRICE_*_USD_PER_MILLION`; for `target_set_size: 201`
  (>200, goal #11's ceiling); for `scenario_trial_min` outside `1..scenario_trial_size`;
  `candidate_cutoff_date` boundary (`2026-03-01` passes, `2026-02-28` raises — via
  `assert_cutoff_margin`, P1.4); **`test_settings_has_no_snapshot_date`** and
  **`…_no_reasoning_effort`** — an unknown key in `config.yaml` raises, proving neither can be
  reintroduced as a tunable.
- **Verify:** `prep/.venv/bin/python -m pytest tests/test_config.py -q`
- **Also update:** none yet — the two cross-language drift checks (`test_model_id_matches_template`,
  `…_model_cutoff…`, `…_judge_confidence_floor…`, `…_reasoning_effort…`) land in **P6.12**, when
  `template/src/config.ts` exists to read. Listed here so they are not forgotten: they belong to
  `test_config.py` but cannot run until P6.

### P1.2 — `logging_.py`
- **Spec:** §1, §3 | **Creates:** `log(message: str) → None`, `configure_logging()`
- **Tests first:** `test_logging.py` — `log()` emits at INFO; `configure_logging()` is idempotent.
- **Why it exists at all:** `log()` is used throughout `prep/` (§3's curation loop, §7's trial) and
  the spec's own review found it *defined nowhere*. A 400-record sweep that prints nothing for 20
  minutes is indistinguishable from a hang, so progress is visible **by default**.

### P1.3 — `reader.py`
- **Spec:** §2 | **Creates:** `stream_annotations(path) → Iterator[dict]`
- **Tests first:** `test_reader.py` — streams a 3-line fixture **without loading the whole file**
  (assert via generator-exhaustion, not a memory profiler); a malformed line is skipped + warned and
  the stream continues; a missing file raises `FileNotFoundError`.
- **Non-negotiable:** the real file is ~1.8 GB (goal). One JSON object per line, streamed. Never
  `json.load()` the file.

### P1.4 — `candidates.py`
- **Spec:** §2 | **Creates:** `ACTIONABLE_UPDATE_TYPES: frozenset[str]`, `SNAPSHOT_DATE`
  (code constant), `is_candidate(rec) → tuple[bool, list[str]]`, `filter_candidates(records) →
  Iterator[dict]`, **`assert_cutoff_margin(candidate_cutoff_date) → None`**
- **Tests first:** `test_candidates.py` — each predicate individually (cutoff boundary at exactly
  `2026-03-01` passes / `2026-02-28` fails; snapshot boundary `2026-07-11` passes / `2026-07-12`
  fails; **`test_snapshot_upper_bound_catches_rot_even_when_valid_flag_lies`** — a `2569-01-01`,
  `valid=True` fixture is rejected by the upper bound alone; each of the 8 actionable types passes
  and `"press release"` fails; `impact_label="medium"` fails; empty `key_requirements` fails);
  **`test_duplicate_ids_deduped`** (first occurrence wins — the sole dedup layer);
  **`test_cutoff_is_derived_from_model`** — with the shipped constants the floor is **exactly
  `2026-03-01`**, and setting `MODEL_CUTOFF` later makes the unchanged cutoff **raise**, naming the
  re-derivation goal #3 requires.
- **Also update:** none — but note `assert_cutoff_margin` is *called by* `load_settings()` (P1.1),
  so P1.1's cutoff test depends on this task. Build P1.4 before P1.1's cutoff case, or stub it.

### P1.5 — `extract.py`
- **Spec:** §2 | **Creates:** `FIELD_MAP: dict[str,str]`, `extract_record(raw) → dict|None`
- **Tests first:** `test_extract.py` — every `FIELD_MAP` dotted path resolves against the real
  sample-record fixture; a missing nested path yields `None`, **not** `KeyError`; a missing `id`
  returns `None`.
- **Constraint:** `FIELD_MAP` is this project's **own** hand-derived copy. Never import
  `carver_showcase.schema` (goal #13; `test_imports.py` enforces it).

### P1.6 — `urls.py`
- **Spec:** §2's tri-state | **Creates:** `UrlStatus` (Literal), `extract_urls(text) → list[str]`,
  `resolve_url(url, cache: dict[str, UrlStatus], timeout=10.0) → UrlStatus`
- **Tests first:** `test_urls.py` — `extract_urls` against the real
  `reg_rules` prose-with-parenthetical-URL sample; **`resolve_url` returns the exact `UrlStatus`
  per case** against an httpx `MockTransport`: `200`/`301→200` → `"resolves"`; **`404`/`410` →
  `"not_found"`** (the only statuses that may ever become failure evidence); **`403`/`429`/`500`/
  `503`/timeout/DNS-error → `"unverifiable"`**; the HEAD→GET retry path; cache memoization.
- **Why the tri-state matters:** fail-closed is right for the ground-truth gate (it *drops* a
  record) and **inverts** on the baseline's citation (it *admits* one). A 403 from a regulator
  blocking datacenter IPs must never read as a fabricated citation.

### P1.7 — `sampling.py`
- **Spec:** §3 | **Creates:** `stratified_sample_sequence(rows, seed=42) → list[dict]`
- **Tests first:** `test_sampling.py` — determinism (same seed → identical sequence);
  proportionality; full-pool coverage (`len(sequence) == len(candidates)` — it returns the whole
  deterministic order; callers take prefixes).

### P1.8 — `scenarios.py`
- **Spec:** §7 | **Creates:** `SCENARIO_A`/`SCENARIO_B` (`ScenarioSpec`), `DOMAIN_BUCKETS`,
  `INDUSTRY_TAG_TO_BUCKET`, `NEGATIVE_CONTROL_TASKS`, `NEGATIVE_CONTROL_ARTIFACTS`,
  `build_task_instance(record, scenario) → dict`, `build_negative_control_prompts(scenario) →
  list[str]`, `is_eligible(record, scenario) → bool`, and the module-private
  `_keyword_eligible_a/_b`, `_jurisdiction_eligible_a`, `_jurisdiction_usable`,
  `_topical_signal_usable`
- **Tests first:** `test_scenarios.py` + `test_scenario_decision.py`'s eligibility cases —
  `_tag_matches_keyword` word-boundary behavior (`"ai"` matches `"Generative AI"`, not
  `"retail"`); a US-jurisdiction AI fixture is **False** for A, `country="DE"` **True**;
  **`test_marketing_alone_not_eligible_for_b`**; **`test_null_country_and_bloc_not_eligible_for_b`**;
  **`test_empty_topical_signal_not_eligible`**; **`test_negative_control_tasks_are_benign`** — none
  contains any scenario keyword; `build_negative_control_prompts` returns **exactly 30**
  (10 topics × 3 artifacts), deterministic and order-stable; `buckets_golden.json` parity.
- **Why `is_eligible` lives here and not in `scenario_decision.py`:** §1 is explicit — `scoring.py`
  imports it, and `scoring → scenario_decision → curate → scoring` would be a cycle. This is the
  homing decision that keeps the DAG acyclic; do not move it.

### P1.9 — `schema.py` + the golden fixtures **[parallel track C]**
- **Spec:** §5 | **Creates:** `BaselineFailure`/`ClearedRecord` (TypedDicts),
  `SCORE_OUTCOME_TO_FAILURE_MODE`, `STAGE_OF_MODE`, `to_json(record) → dict`,
  `validate_cleared_record(obj) → tuple[bool, list[str]]`,
  **`predicts_stage_a_violation(record) → bool`**
- **Also creates:** `prep/tests/fixtures/scoring_golden.json` with **four named groups** —
  `citation_date_cases`, `judge_cases` (incl. out-of-range `5.0`/`-0.2`/`NaN`), `obligation_cases`
  (incl. exactly one `prep_only: true` case — the `not_applicable` one the 3-arg TS port cannot
  reach), `stage_a_predicate_cases`; plus `narrowing_golden.json` and `buckets_golden.json`.
- **Tests first:** `test_schema.py` — `validate_cleared_record` rejects an `attestation` other than
  `"approved"`, an unlisted extra key, empty `baseline_failures`, a `BaselineFailure.stage`
  disagreeing with `STAGE_OF_MODE[mode]`; **`test_no_unreviewed_records_in_cleared_dir`**;
  **`test_predicts_stage_a_violation`** (citation-only → False; missed_obligation + all three
  confirmations → True; any one confirmation False/None → False).
- **Also update:** the fixtures are **byte-identical duplicates** across the seam. When this task
  creates them under `prep/tests/fixtures/`, it **also** copies them to
  `template/tests/fixtures/` and P1.10 asserts they match. Creating one without the other is the
  exact drift this mechanism exists to prevent.

### P1.10 — `test_fixture_parity.py`
- **Spec:** §12 | **Tests:** **`test_golden_fixtures_are_byte_identical`** — reads all three
  fixtures from both sides as **bytes** and asserts equality.
- **Why:** each side otherwise tests only its own copy; if one gains a case the other lacks, both
  suites stay green while the parity guarantee silently weakens. This is the one test that reads
  across the seam — and it reads **data**, never code, so goal #1 is untouched.

### P1.11 — `budget.py` (the leaf everything reserves against)
- **Spec:** §3 | **Creates:** `MODEL_MAX_CONTEXT_TOKENS`, `REQUEST_OVERHEAD_ALLOWANCE_TOKENS`,
  `PINNED_PRICE_INPUT_USD_PER_MILLION`, `PINNED_PRICE_OUTPUT_USD_PER_MILLION`, `REASONING_EFFORT`,
  `MODEL_CUTOFF`, `CUTOFF_MARGIN_DAYS`, `CUTOFF_MARGIN_IS_INCLUSIVE`, `UNBILLED_STATUS_CODES`,
  `build_request_payload(...)`, `estimate_tokens(text)`, `reservation_basis_tokens(payload)`,
  `SpendBudget` (`.reserve` → `Reservation`, `.max_call_cost`, `.assert_no_open_reservations`),
  `Reservation` (`.settle` / `.release` / `.finalize_unknown` / `.finalize_unusable_usage`),
  `terminal_for_exception(reservation, exc)`, `BudgetExhausted`, `BudgetPoisoned`
- **Tests first:** `test_budget.py` — **one test per row of §3's lifecycle table**, each asserting
  BOTH invariants (`spend_so_far_usd <= ceiling_usd` **and** `>= true billed`):
  `test_settle_books_actual_and_returns_headroom`;
  **`test_release_returns_the_full_hold`** (a 400-shaped exception via `terminal_for_exception`);
  **`test_finalize_unknown_keeps_the_full_hold`** (timeout-shaped);
  **`test_retry_does_not_double_count`** — the exact leak: a timeout then a successful retry leaves
  spend = retry's true cost **plus** the first attempt's provider-max hold, never two full holds;
  **`test_double_terminal_raises`**; **`test_assert_no_open_reservations`**;
  **`test_ceiling_holds_at_provider_maximum`**; **`test_settle_poisons_when_tight_estimate_is_beaten`**;
  the **unbookable-usage battery** (`settle(None)`, `{}`, one key missing, non-numeric, `True`
  (bool-is-int), negative, and **`test_usage_above_provider_cap_poisons`**) — each asserting the
  handle ends terminal, the hold is retained, `BudgetPoisoned` raises, and a second terminal op
  then raises; **`test_settle_failure_does_not_reach_terminal_for_exception`** (the `else`-block
  placement); **`test_tiny_ceiling_rejects_every_call`**;
  **`test_reservation_includes_overhead_allowance`**;
  `SpendBudget(price_in=0.001, …)` raises `ValueError`.
- **Verify:** `prep/.venv/bin/python -m pytest tests/test_budget.py -q`
- **Why this module is a leaf:** §1's DAG. `probe`/`judge`/`curate` all need `SpendBudget`; homing
  it in `curate.py` (an earlier spec draft did) created a real `probe → curate → probe` cycle.
  `test_imports.py` (P1.0) asserts its intra-package import set is **empty**.

### P1.12 — `openai_client.py`
- **Spec:** §3, §15 | **Creates:** `load_env(dotenv_path) → None`, `make_client() → openai.OpenAI`
- **Tests first:** missing `.env` logs a WARNING and proceeds (the key may be in the shell env);
  absent `OPENAI_API_KEY` raises `KeyError` with a clear message.
- **The only secret this project has is `OPENAI_API_KEY`** (goal #9). No Carver key, no Anthropic
  key, no Mastra token. This module is the only place a key is read.

### P1.13 — `prompts/*.md`  **[parallelizable]**
- **Spec:** §3, §4 | **Creates:** all six, with their exact placeholders:
  `stage_a_system.md` (`{{PERSONA}} {{COMPANY}} {{JURISDICTION_PHRASE}} {{DOMAIN_PHRASE}}
  {{TASK_VERB_PHRASE}}`), `stage_a_user.md` (`{{TASK_INSTANCE}}`), `stage_b_system.md`,
  `stage_b_user.md` (`{{FOLLOWUP_QUESTION}}`), `judge_system.md`, `judge_user.md`
  (`{{RECORD_SUMMARY}} {{DRAFT_TEXT}}` / `{{OBLIGATIONS_JSON}}`).
- **Fair-test discipline is the whole point:** §3's MAY/MUST-NOT list governs what a prompt may
  contain. `test_probe.py::test_task_instance_excludes_leaked_fields` (P2.1) is what enforces it.

### P1.14 — Python code review gate
- **Do:** run the **python-code-reviewer** agent over everything P1 created; have the
  **python-expert** fix findings. (Repo convention: after *each* Python change. In practice: at
  each phase boundary, and this is the first.)

---

# PHASE 2 — `prep/` LEVEL 1–2 (stubbed clients, still zero billed calls)

**Bills: nothing.** Every call goes through a stub. Ends green when the full curation loop runs
end-to-end against canned responses.

### P2.0 — `tests/stubs.py` FIRST
- **Spec:** §14 | **Creates:** `StubOpenAIClient` (configurable canned response per call index),
  `RecordingStubClient` (captures kwargs; asserts **no `temperature`** param and the correct
  `reasoning_effort`/`max_completion_tokens`), `TruncatingStubClient` (`finish_reason="length"`).
- **Note:** in `tests/stubs.py`, importable — **not** `conftest.py` — avoiding the `tests/` package
  self-import trap documented in `docs/LESSONS.md`.

### P2.1 — `probe.py`
- **Spec:** §3 | **Creates:** `run_stage_a(client, record, scenario, cfg, budget) → StageAResult`,
  `run_stage_b(...) → StageBResult`
- **Tests first:** `test_probe.py` — **`test_task_instance_excludes_leaked_fields`** across a
  fixture battery (rubric 11's fair-test assertion: the prompt may contain the persona, company, a
  `DOMAIN_BUCKETS` phrase and a jurisdiction phrase — and **nothing** from the record);
  Stage B's structured response parses via `StubOpenAIClient`.
- **Depends on:** P1.11 (`SpendBudget`, `build_request_payload`), P1.8 (`scenarios`).
- **Every call follows §3's lifecycle verbatim:** `build_request_payload` → `budget.reserve` → the
  SDK call with **that same dict** → `settle(usage)` on the `else`, `terminal_for_exception` on the
  `except`. The `else`-block placement is load-bearing (Python does not route an `else`-block
  exception to that `try`'s `except`), so a `BudgetPoisoned` from `settle` cannot double-terminate.

### P2.2 — `judge.py`
- **Spec:** §4 | **Creates:** `JUDGE_RESPONSE_SCHEMA` (with `confidence: {minimum: 0, maximum: 1}`),
  `JudgeObligationInput`/`JudgeVerdict`/`JudgeResult`, `run_judge(client, obligations, draft_text,
  cfg, budget) → JudgeResult`, `parse_and_validate_verdicts(raw_response, requested_ids) →
  JudgeResult`
- **Tests first:** `test_judge.py` — duplicate `obligation_id` → first wins; omitted id →
  `"uncertain"`, confidence `0.0`, `applies_to_draft=False`, `omission_material=False`, **never**
  `"violation"`; hallucinated id → dropped; malformed JSON → retry once → all-omission fallback;
  **`test_out_of_range_confidence_discarded_not_clamped`** — `5.0` yields `uncertain`/`0.0`/
  `is_failure=False`, **explicitly not** `1.0` (clamping would clear the 0.7 floor and admit a
  record on garbage); same for `-0.2`, `NaN`, `Infinity`, `"0.9"`; `0.0` and `1.0` accepted; the
  synthesized rationale distinguishes out-of-range from omitted.
- **The schema bound is not the enforcement point.** OpenAI accepts `minimum`/`maximum` but does
  **not** structurally enforce them; `parse_and_validate_verdicts` step 3 is the only real check.

### P2.3 — `scoring.py`
- **Spec:** §4 | **Creates:** `score_citation(stage_b, record) → CitationScore`,
  `parse_baseline_date(raw) → str|None`, `score_compliance_date(stage_b, record, citation) →
  DateScore` (**three** args — the spec's F-round heading fix), `score_missed_obligation(record,
  scenario, judge_result, obligation_id) → ObligationScore`, `passes_failure_bar(citation, date,
  obligation) → tuple[bool, list[str]]`
- **Tests first:** `test_scoring.py` — one test per outcome value against `scoring_golden.json`,
  asserting `is_failure` is **True for exactly** `citation_fabricated` / `date_wrong` /
  `violation-above-floor-with-both-flags-true`, and **False for every other outcome** including
  `citation_alternative_real`, **`citation_unverifiable`**, `date_missing`, **`date_unparseable`**,
  `date_uncertain_attribution`; `score_missed_obligation` returns `not_applicable` without
  consulting the judge at all when `is_eligible` is False; `score_compliance_date` with a
  non-`citation_correct` citation always returns `date_uncertain_attribution`; failure-bar OR-logic;
  `SCORE_OUTCOME_TO_FAILURE_MODE`/`STAGE_OF_MODE` round-trip over exactly the 3 closed values.
- **`parse_baseline_date` is not optional polish:** `"September 1, 2026"` is a **correct** answer in
  the wrong shape; a raw string compare admits the record on evidence the baseline got it *right*.
  Ambiguous forms (`"01/09/2026"`) resolve to `None` → `date_unparseable`, never a guess.

### P2.4 — `curate.py`
- **Spec:** §3 | **Creates:** `CurationResult`, `probe_and_score_one(...) → ProbeAndScoreResult`,
  `_cap_stop_reason(survivors, probed, cfg) → str|None`, `run_curation(client, candidates, scenario,
  cfg, budget, exclude_ids=frozenset()) → CurationResult`
- **Tests first:** `test_curate.py` — all four stop conditions;
  **`test_survivor_ceiling_exact_at_batch_crossing`** (enter a 40-batch at 199 survivors → asserts
  `len(survivors) == target_set_size` **exactly**, never 200+n);
  **`test_sweep_cap_exact_at_batch_crossing`**; **both re-run across `probe_batch_size ∈ {1,7,40}`
  asserting identical counts** (batch size cannot influence a cap); a `BudgetExhausted` can stop
  mid-record and that record counts toward neither `probed` nor `survivors`;
  **`test_excluded_ids_are_never_probed`** (§7's winner's-curse fix).
- **The caps bind per-record, not per-batch.** A batch-boundary check overshoots by up to
  `probe_batch_size` — 39 records past goal #11's stated ceiling. Batching is now a **logging
  cadence only**.

### P2.5 — Python code review gate (as P1.14)

---

# PHASE 3 — `prep/` LEVEL 3

### P3.1 — `scenario_decision.py`
- **Spec:** §7 | **Creates:** `ScenarioDecision` (TypedDict), `decide_scenario(client, trial_pool,
  cfg, budget) → ScenarioDecision`, `strength(result) → float`, `mean_strength(probed) → float`
- **Tests first:** `test_scenario_decision.py` —
  **`test_budget_exhaustion_truncates_both_arms_equally`** (exhaustion mid-round 7 → both arms at 6,
  the in-flight round discarded whole, and **A is not declared winner off a fuller arm**);
  **`test_insufficient_trial_returns_no_winner`** (below `scenario_trial_min` → `outcome=
  "insufficient_trial"`, `winner is None`, `run_prep` locks no scenario and exits 0);
  **`test_small_eligible_pool_is_sufficient_when_fully_probed`**;
  **`test_discarded_round_drops_both_arms`**; `mean_strength` tie → `A`; `B` wins on strictly higher
  MEAN even with a smaller trial; evidence-file shape.
- **The arms interleave.** Running A to completion then B means any budget stop truncates B alone
  and hands the win to A — invisibly, since A is also the tie-break. One record each, in lockstep.

### P3.2 — `generate_template_config.py`
- **Spec:** §7 | **Creates:** `TemplateConfigBundle`, `firm_profile_for_record(record) → dict`
  (**camelCase keys** — it is serialized straight into a TS object literal),
  `narrow_obligations_pure(firm_profile, cleared_records) → list[str]` (the Python port of §9a),
  `emit_template_config(cleared_records, decision) → TemplateConfigBundle`
- **Tests first:** `test_generate_template_config.py` — `test_trigger_tie_broken_by_id_ascending`;
  **`test_trigger_never_citation_only`** (the highest-failure-count record carries only
  citation/date evidence; the 1-mode `missed_obligation` record is chosen — **evidence type gates
  candidacy before strength ranks it**); **`test_raises_when_no_stage_a_evidence`** (ValueError
  naming the cause; writes **no** files); **`test_trigger_skips_crowded_out_candidate`**; step 7's
  narrowing assertion fires on a non-matching profile; **`test_narrowing_golden_parity`**.
- **Also update:** this task writes **four** `.tmpl` fragments under `prep/templates/` —
  `config_ts_fragment.tmpl`, `firm_profile_ts_fragment.tmpl`, `persona_ts_fragment.tmpl`,
  `prompts_ts_fragment.tmpl`. The fourth renders `scenario/prompts.ts` **in full**
  (`buildStageAPrompt`, `buildStageBPrompt`, `INDUSTRY_TAG_TO_BUCKET`, `DOMAIN_BUCKETS`,
  `SCENARIO_TASK_TEMPLATES`, `NEGATIVE_CONTROL_PROMPTS`). §8 resolves that module as **generated**,
  not hand-authored — that is what makes §12's eval ask the same question the evidence was recorded
  for.

### P3.3 — Python code review gate

---

# PHASE 4 — `review.py`, the clearance CLI

### P4.1 — `review.py`
- **Spec:** §6 | **Creates:** `HumanReview` (TypedDict), `present_for_review(record,
  resolving_citations) → str`, `select_citation(resolving_citations) → tuple[str,str]`,
  `ask_obligation_confirmations(record) → dict[str,bool]|None`, `record_signoff(record, reviewer,
  obligation_confirmations) → ClearedRecord`, `record_rejection(record, reviewer, reason) → None`
- **Tests first:** `test_review.py` — `record_signoff` has **no parameter capable of overriding**
  `title`/`why_it_matters`/any extracted field (a `TypeError` on an extra kwarg — the signature
  takes only `record`/`reviewer`/`obligation_confirmations`); citation auto-selected with no prompt
  when exactly one URL resolves, prompted when >1; `ask_obligation_confirmations` returns `None`
  immediately when `missed_obligation` is absent; **any single `False` among the three questions
  makes the CLI refuse to reach `approve`** (routes to `record_rejection`);
  `validate_cleared_record` rejects a `human_review` with a stray confirmation.
- **This is the publication gate** (goal hard constraint: *never ship a record that has not been
  human-reviewed*). There is no batch-approve flag in code or config, and adding one is the
  "waiving human review" row of §6's anti-padding table.

### P4.2 — Python code review gate

---

# PHASE 5 — `run_prep.py`, stubbed end-to-end

### P5.1 — `run_prep.py`
- **Spec:** §3's pinned entrypoint | **Creates:** `main(argv=None) → None` with the exact structure
  §3 pins: `load_settings` → `load_env` → `make_client` → `SpendBudget` → **`try:`** filter
  candidates → `decide_scenario` → write evidence → **`if outcome == "insufficient_trial"`: report
  and return** → filter by `is_eligible` → `run_curation(exclude_ids=…)` → `report_curation` →
  **`finally:` `budget.assert_no_open_reservations()`** + log spend.
  Plus the `--replay`, `--emit-template-config`, `--verify-cleared` argv branches.
- **Tests first:** `test_run_prep.py` — `main()` filters through `is_eligible` **before**
  constructing `run_curation`'s input; **`test_reservation_audit_runs_on_every_exit_path`** — the
  `finally` fires on **all four** exits (clean finish, `insufficient_trial` early return,
  `BudgetExhausted` stop, unexpected exception); **`test_insufficient_trial_short_circuits`** —
  writes the evidence file, calls `run_curation` **zero** times, returns 0.
- **`report_curation`'s output fields are pinned** (§3) — including that `survivors/probed` is
  **success-conditioned** (curation stops at target, so the rate is biased upward) and that its
  denominator is the **scenario-eligible subset**, not the goal's headline 8,260.
- **Verify:** `prep/.venv/bin/python -m pytest tests/ -q` — **the entire `prep/` suite green, zero
  billed calls.** This is the phase gate.

### P5.2 — Zero-spend proof
- **Do:** confirm no test ever constructs a real client. `grep -rn "make_client()" tests/` returns
  nothing; every test injects a stub. **`OPENAI_API_KEY` should be unset while running the suite** —
  if the suite passes without a key, it made no calls. That is the check, and it is cheap enough to
  run at every phase gate.

---

# PHASE 6 — `template/` (synthetic fixture; still zero billed calls) **[parallel track B]**

**Bills: nothing** — except `comparisonWorkflow.test.ts`, which is **excluded from `test:unit`**
and deferred to P6.11. Ends green when `npm run test:unit` passes.

### P6.1 — Synthetic cleared-set fixture
- **Spec:** §5 | **Creates:** `template/src/data/cleared-set.json` — a **synthetic**,
  schema-conforming set (~6 records) covering: a `missed_obligation` record with all three
  confirmations; a citation-only record; a record with both; one that will be `crowdedOut`; a
  non-ASCII regulator name; a null-`compliance_date` record.
- **Why synthetic and why now:** this is Fact 2. Every template module can be built and proven
  against it, so the real run (P7) is paid **once**, against a consumer already known to work. The
  file is replaced wholesale in P8; `schema.test.ts` is what makes the swap safe.

### P6.2 — `schema.ts` + `config.ts` + `firmProfile.ts`
- **Spec:** §5, §8 | **Creates:** `BaselineFailureSchema`, `ClearedRecordSchema` (`.strict()`),
  `ClearedRecord`, `StageBResponseSchema`, **`predictsStageAViolation`** (schema.ts — **not**
  `GuardrailVerdictSchema`, whose sole owner is `judge/contract.ts`); `MODEL_ID`, `MODEL_CUTOFF`,
  `SNAPSHOT_DATE`, `JUDGE_CONFIDENCE_FLOOR`, `REASONING_EFFORT`, `MAX_OUTPUT_TOKENS`,
  `GENERATION_CONFIG` (config.ts — **no `MAX_PROCESSOR_RETRIES`**); `FirmProfileSchema`,
  `FirmProfile`, `DEMO_FIRM_PROFILE`, `firmProfileForRecord` (firmProfile.ts)
- **Tests first:** `schema.test.ts` (the vendored file parses for every record);
  `config.test.ts` (`test_generation_step_actually_ran` — `DEMO_TRIGGER_RECORD_ID !== ""` and
  resolves; **`SCENARIO_PERSONA_INSTRUCTIONS !== ""`**, since its declared default is the empty
  string and a forgotten generation step would ship an agent with **no persona** — a silently
  different experiment, not a crash; `GENERATION_CONFIG` is the same object both agents hold;
  `MAX_PROCESSOR_RETRIES` is **not exported**); `firmProfile.test.ts`.
- **Note:** P6.2's `config.test.ts` cases that depend on generated constants will **fail until
  P8.2**. That is correct and intended — they are the check that the generation step ran. Mark them
  `.skip` with a `// unskip in P8.2` comment, and **P8.2 unskips them**. (Listing this here so the
  unskip is a named obligation, not a memory.)

### P6.3 — `judge/contract.ts` then `judge/callJudge.ts`
- **Spec:** §8 | **Creates:** `JUDGE_SYSTEM_PROMPT`, `renderJudgeUserPrompt`,
  `GuardrailVerdictSchema` (**sole owner**; `confidence: z.number().min(0).max(1)`),
  `JudgeObligationInput`/`JudgeResult`, `parseAndValidateVerdicts` (contract.ts — **zod only**,
  never an agent, never a scorer); `runJudge(obligations, draftText)` (callJudge.ts — the **only**
  place `judgeAgent` is ever invoked)
- **Tests first:** `scorers.test.ts`'s `judge_cases` group against `parseAndValidateVerdicts`.
- **Order matters:** `contract.ts` first (it is the leaf that breaks the `judgeAgent ↔ scorers`
  cycle), then `callJudge.ts` (which imports it *and* the agent, one-way).

### P6.4 — `agents/sharedConfig.ts` + the three agents
- **Spec:** §8 | **Creates:** `SHARED_AGENT_CONFIG` (`instructions`/`model`/`defaultOptions` — the
  ONE object both compared agents spread); `baselineAgent`, `guardedAgent` (`...SHARED_AGENT_CONFIG`
  + `outputProcessors: [new CarverGuardrail()]` — **the only difference between the arms**),
  `judgeAgent`
- **Tests first:** `carverGuardrail.test.ts` —
  **`test_requestContext_cannot_reach_either_prompt`**: `SHARED_AGENT_CONFIG.instructions`/`.model`
  are **static values, not functions** (a dynamic config function is the only documented path from
  `requestContext` into a prompt); via the public accessors, `getInstructions({requestContext})`
  returns the unchanged constant and does **not** contain the profile's country/sector;
  `listTools()` is empty; the two arms resolve identically.
  **`test_guarded_agent_has_no_processor_retries`** — `maxProcessorRetries` undefined.
- **Why this is a controlled-experiment guard, not a lint:** if `requestContext` reached the
  prompt, the guarded arm would draft *knowing the firm's jurisdiction and sector* while the
  baseline drafts blind — goal #9's explicitly fatal case, and it would **look like success**.

### P6.5 — `tools/narrowObligations.ts`
- **Spec:** §9a | **Creates:** `narrowObligations` (Tool), `narrowObligationsPure(firmProfile,
  clearedSet) → string[]`
- **Tests first:** `narrowObligations.test.ts` — zero-required-match; exactly-one; >5 (ranking
  exercised); jurisdiction-only with no industry/function overlap **excluded** (required-AND);
  **`test_every_cleared_record_is_relevant_to_its_own_profile`** (§9a's proof, over the real
  vendored set); **`test_null_country_and_bloc_record_cannot_match`**;
  **`test_narrowing_golden_parity`**; `test_demo_trigger_record_survives_narrowing` (**skip until
  P8.2**, same as P6.2).
- **`urgencyWeight` uses `SNAPSHOT_DATE`, never `Date.now()`** — narrowing must be deterministic on
  every machine, forever.

### P6.6 — `processors/tripwireContainment.ts` **(goal #8's KNOWN RISK — resolved HERE, early)**
- **Spec:** §10, §12 | **Creates:** `TripwireOutcome`, `normalizeDelivery(call) →
  Promise<TripwireOutcome>`, `isTripWireError(err)` (**sole owner** — not `carverGuardrail.ts`)
- **Tests first:** `tripwireContainment.test.ts` —
  **`test_both_tripwire_forms_normalize_identically`**: a stubbed agent that **returns**
  `{tripwire}` and one that **throws** `TripWireError` yield the same `{tripped: true, reason,
  processorId, metadata}`; a non-tripwire error re-throws untouched; a clean call →
  `{tripped: false, text}`. Then **both mappings**: guarded → `GuardedResultSchema`,
  delivery → `DeliveryResultSchema`.
- **This is where goal #8's risk gets resolved empirically, and it is deliberately early.** The
  goal says *"Verify this in the first hour of the template stage; do not assume either way."* The
  unit test pins both forms with stubs (free, instant); the **live** proof is P6.11.

### P6.7 — `processors/carverGuardrail.ts`
- **Spec:** §9 | **Creates:** `CarverGuardrail` (class), `AuditEntry`, `AuditWriter`,
  `FileAuditWriter`; the three stages (narrow → verdict → enforce)
- **Tests first:** `carverGuardrail.test.ts` — a synthetic verdict drives each of high/medium/low
  through enforcement (**medium/low are unit-test-only** — see the Goal-issue note in §11 below);
  **audit writes** asserted via an injected stub `AuditWriter`, including the high/abort path
  (catch the thrown tripwire, check the stub was called **before** the throw); zero-violation → no
  write; **`test_multi_violation_reports_full_set`** — a stubbed judge returning three violated
  obligations asserts `violated_obligation_ids` lists all three **in narrowing-rank order**, that
  `record.id` is the first, and the audit entry carries the same array;
  **`test_judge_parse_failure_passes_through`** — a judge throwing on both attempts returns the
  draft **unchanged**, calls `abort()` never, writes no audit entry, propagates **no exception**.
- **Depends on:** P6.3 (`runJudge`), P6.5 (`narrowObligationsPure`), P6.2 (`schema.ts`).
  **Not** `agents/judgeAgent.ts` — the guardrail delegates through `callJudge.ts`, the only
  permitted path to that agent.

### P6.8 — `workflows/compareWorkflow.ts`
- **Spec:** §10 | **Creates:** `draftStep`, `guardedStep`, `reportStep`, `GuardedResultSchema`
  (discriminated union + `superRefine` on the union — `z.discriminatedUnion` needs plain
  `ZodObject` members, so the refinement wraps the union), `ComparisonReportSchema`,
  `compareWorkflow` (**with `requestContextSchema: z.object({firmProfile: FirmProfileSchema})`** —
  validated at `run.start()`, and what gives Studio a schema-driven form)
- **`guardedStep` calls `normalizeDelivery` and maps** — it does **not** inline a `try/catch`.
  `buildBlockedResult` recomputes `narrowObligationsPure(firmProfile, vendoredClearedSet)` as the
  authoritative candidate set (metadata cannot vouch for itself), requires every violated id to be a
  unique member **in rank order**, and **derives** the display record from the vendored set rather
  than trusting metadata's copy.
- **Tests first:** the negative battery in `comparisonWorkflow.test.ts` (all non-billing, run now):
  duplicate id; an id that is not a vendored record; **`test_known_but_not_narrowed_id_rejected`**;
  ids out of rank order; **`test_forged_record_metadata_is_ignored`** (a forged title/citation
  yields the **vendored** record's real values).

### P6.9 — `evals/deliveryWorkflow.ts` + `evals/scorers.ts`
- **Spec:** §12 | **Creates:** `DeliveryInputSchema` (incl. **`recordId`** — the ground truth rides
  in the workflow input, because a scorer's `run` carries `runId`/`input`/`output`/`requestContext`
  and **no `groundTruth`**), `DeliveryResultSchema`, `deliveryStep`, `deliveryWorkflow`,
  `stageBStep`, `stageBWorkflow`; `recordFor`, `extractScores`, `LedgerRow`, `DeliveryScorer`
  (the union — **including `blockedScorer`**), the five scorers (`unsafeShipScorer`,
  `blockedScorer`, `guardedCatchScorer`, `benignPassScorer`, `stageBScorer` — all
  `createScorer<In, Out>` **generics**, not a `type:` object), `partitionForGuardedEval`,
  `stageBRecords`, `runArm`, `runNegativeControl`, `runStageBEval`, `runScoreboard` (**no
  parameter**)
- **Tests first:** `evals.test.ts`'s non-billing cases —
  **`test_partition_is_disjoint_and_total`**;
  **`test_knowledge_only_records_are_never_sent_to_the_guarded_agent`**;
  **`test_paired_row_uses_one_scorer`** (both arms carry `ships-violating-draft`, and their ledgers'
  `recordId` sequences are identical element-for-element);
  **`test_ledger_matches_runEvals_averages`** (`|mean − avg| < 1e-9` — a **tolerance**, since
  concurrent items make summation order non-deterministic);
  **`test_negative_control_contract`** (`length === 30`, deterministic, benign, in-scenario,
  narrowing non-empty); **`test_delivery_scorer_union_is_complete`**;
  **`test_blanket_guardrail_fails_the_suite`** — a stubbed always-aborting processor **passes** the
  unsafe-ship and catch assertions and **fails** the benign-task assertion.
- **That last test is the point of the whole harness.** Without the negative control, a processor
  whose enforcement is `abort()` — no narrowing, no judge, no Carver data — scores a perfect 0.00
  unsafe-ship and 1.00 catch and passes everything else. **Never weaken or skip it** (rubric 23).

### P6.9b — `prompts.test.ts` — fair-test discipline, template-side
- **Spec:** §8 | **Tests:** **`test_prompt_builders_never_leak`** — over **every** vendored record
  and **both** builders (`buildStageAPrompt`, `buildStageBPrompt`), assert no `title` / `objective`
  / `what_changed` / `why_it_matters` / `citation.url` / `citation.name` / `compliance_date` /
  `key_requirements` substring appears in the prompt, and that a `DOMAIN_BUCKETS` phrase does;
  **`buckets_golden.json` parity** — `INDUSTRY_TAG_TO_BUCKET` reproduces every case prep's
  `test_scenarios.py` asserts, including the unmapped-tag default.
- **Why this is its own task and not a footnote:** §3's MUST-NOT list and
  `test_task_instance_excludes_leaked_fields` existed **only in `prep/`**. But
  `buildStageAPrompt(record: ClearedRecord)` receives an object carrying every field §3 forbids,
  and it drives the demo, the containment test and **both eval arms**. Nothing structural stopped a
  future edit from interpolating `record.title` "to make the prompt more realistic" and silently
  leaking the answer into the question the whole experiment turns on. The rule binds both halves or
  it binds neither.
- **Sequencing note:** `scenario/prompts.ts` is **generated** in P8.2, so this test's real subject
  arrives then. Write it in P6 against the synthetic fixture's hand-written stand-in module, and it
  starts guarding the generated file the moment P8.2 overwrites it — no `.skip` needed, because the
  assertion is about *content*, not about the generation having run.

### P6.10 — `report/`, `mastra.ts`, `scripts/`
- **Spec:** §11, §8 | **Creates:** `report/reportTemplate.ts` (`renderReportHtml`, `escapeHtml` —
  inline CSS, **no external refs**), `report/generateHtmlReport.ts`; `mastra.ts` — `import
  "dotenv/config"` **first**, then `new Mastra({agents: {baselineAgent, guardedAgent, judgeAgent},
  workflows: {compareWorkflow, deliveryWorkflow, stageBWorkflow}})`; `scripts/demo.ts` (with the
  non-blocking diagnosis + exit codes 1/2), `scripts/printPrompt.ts`
- **Tests first:** `mastra.test.ts::test_all_targets_are_registered` — all three workflows resolve
  and each eval workflow's step can reach `mastra.getAgent("baselineAgent")`.
  **All three workflows must be registered or `npm test` cannot run at all** — the eval steps call
  `mastra.getAgent(...)`, and an unregistered workflow's step context has no `mastra`.
  `evals.test.ts` — report has no external refs; rejects a non-blocked result; escapes injected
  `<script>`; renders **both** real branch outputs plus the matching record.
- **Also update:** `template/README.md` (P6.13) states that Studio lists three workflows and that
  `compareWorkflow` is the demo — the Studio-clutter cost of registration is paid in docs.

### P6.11 — **The live tripwire-containment proof** *(the ONLY billed call before Phase 7)*
- **Spec:** §10, rubric 15 | **Runs:** `comparisonWorkflow.test.ts` against the **synthetic**
  fixture, with a real `OPENAI_API_KEY`.
- **Cost:** ~2 calls, **< $0.01**. Negligible, and it buys the answer to goal #8's KNOWN RISK
  *empirically* rather than by assumption.
- **Asserts:** `result.status === "success"` (**not** `"tripwire"` — the core assertion);
  `guarded.blocked === true`; non-empty `blocked_draft`/`reason`; `processorId ===
  "carver-guardrail"`; `violated_obligation_ids` **contains** the trigger id; `record.id ===
  violated_obligation_ids[0]`; `baseline.text` truthy (**the baseline branch completed
  independently**).
- **If a tripwire DOES propagate and kill the run:** stop and report. §10's dual-layer containment
  is designed to prevent exactly this, and if it does not hold, the comparison workflow's shape is
  wrong and no amount of later work fixes it. This is why it is here and not in Phase 9.

### P6.12 — Cross-language drift checks (now that `config.ts` exists)
- **Spec:** §8, §2 | **Creates (in `prep/tests/test_config.py`):**
  `test_model_id_matches_template`, `test_model_cutoff_matches_template`,
  `test_judge_confidence_floor_matches_template`, `test_reasoning_effort_matches_template` — each
  reads `template/src/config.ts` **as text**, regex-extracts the literal, and asserts equality with
  prep's constant.
- **Why text and never import:** the two halves are different languages and different venvs (goal
  #1/#13). Reading as text is the only safe crossing, and it is the same trick `prep/templates/`
  uses to *write* those files.

### P6.13 — `template/README.md`
- **Spec:** §11 | **Creates:** the required content §11 tables: quickstart (`npm install` → key in
  `.env` → `npm run dev`); **baseline model & cutoff verbatim** (`openai/gpt-5.6-sol`, cutoff
  `2026-02-16`, snapshot `2026-07-11`, every record `2026-03-01`+) **and why** (the flagship,
  deliberately the *strongest* baseline); provider-swap (one line in `config.ts`, and the cutoff
  must be **re-derived**); the Studio path (workflow → run form → prompt from `npm run demo:prompt`
  → `requestContext.firmProfile`); the scoreboard; dataset provenance; **severity-ladder
  coverage** — plainly, that every shipped record is `impact_label == "high"` by construction so
  `medium`/`low` are **unit-test-only**; known limitations.
- **Tests first:** `README.test.ts` — the file exists and contains the literal `MODEL_ID`,
  `MODEL_CUTOFF`, `SNAPSHOT_DATE` read as text from `config.ts`. **Goal #9's disclosure is a test
  failure when it drifts**, not a documentation aspiration.
- **Why `template/` needs its own README:** goal #9 names *the template README* twice, and goal #1
  requires `template/` be trivially extractable. A root-level README does not travel with an
  extraction — Mastra would receive a repo with zero setup instructions and **zero model/cutoff
  disclosure**, destroying what goal #9 calls the defence against the cherry-picking charge.

### P6.14 — Phase gate
- **Verify:** `cd template && npm run test:unit` — green. `npm run typecheck` — green.
  `grep -rn "carver-showcase\|\.\./prep\|mastra_prep" template/src template/tests` — **no hits**
  (goal #9 / success criterion 9).

---

# PHASE 7 — THE REAL RUN *(the money step)*

**Bills: ~$17 typical, ~$93.5 worst case, against the hard $120 ceiling.**

### R7.1 — Preconditions (all must hold; do not start otherwise)
- `prep/.venv/bin/python -m pytest tests/ -q` — **entire suite green**.
- `cd template && npm run test:unit` — green; P6.11's live containment proof passed.
- `prep/.env` has a real `OPENAI_API_KEY`.
- `config.yaml` reviewed: `total_spend_ceiling_usd: 120.0`, `probe_max_records: 400`,
  `target_set_size: 200`, `scenario_trial_size: 30`.
- `../carver-showcase/data/annotations.jsonl` exists and is **read-only** to us
  (`annotations_path` resolves — the **four**-`../` value, P0.3).

### R7.2 — Dry run on a tiny cap *(the shakeout — keeps real spend minimal)*
- **Do:** temporarily `probe_max_records: 5`, `scenario_trial_size: 2`, then
  `prep/.venv/bin/python run_prep.py`.
- **Cost:** ~14 calls, **< $1**.
- **Watch:** the `log()` progress line advances; `data/scratch/probe_log/` fills with one JSON per
  `(record, stage)`; `data/scratch/scenario_decision.json` appears with both arms populated; the
  final spend line is plausible.
- **Why a dry run at all:** the code is fully stub-tested, but stubs cannot prove the *prompt
  templates render sensibly against real corpus prose*, nor that real records survive the URL gate.
  This is the cheapest possible way to learn that, and it is the difference between discovering a
  bad prompt at $1 and at $17.
- **Then:** restore the real caps.

### R7.3 — The scenario trial + curation
- **Command:** `prep/.venv/bin/python run_prep.py` (from `prep/`)
- **Expected:** ~$17 typical. `decide_scenario` runs first (60 records, ~$2.30), writes
  `scenario_decision.json`, locks a winner; curation then sweeps up to 400 **fresh** records
  (`exclude_ids` = the winner's trial ids — §7's winner's-curse fix).
- **What "good" looks like:** `stop_reason` is `target_reached` or `sweep_cap` (**not**
  `spend_ceiling`); survivors ≥ ~20; `stage_a_survivor_counts[winner] ≥ 1`; the spend line well
  under $120.
- **What to watch for, and what each means:**
  | Observation | Meaning | Action |
  |---|---|---|
  | `stop_reason="spend_ceiling"` | The ceiling bound before the sweep finished | Report actual spend; do **not** raise the ceiling reflexively — check first whether a prompt is pathologically long |
  | `BudgetPoisoned` | An estimate assumption broke (§3) | **Stop.** Report. This is the ledger saying it can no longer predict; it is a bug, not a budget event |
  | `outcome="insufficient_trial"` | The trial could not support a winner | Report per §7's Goal-issue callout. **Do not** apply the A tie-break to a trial that did not happen |
  | `stage_a_survivor_counts[winner] == 0` | Valid dataset, **no live demo possible** | Escalate — `emit_template_config` will raise in P8.2 |

### R7.4 — Human review *(BLOCKING, MANUAL, cannot be automated)*
- **Command:** `prep/.venv/bin/python run_prep.py --review`
- **Per record:** read the evidence beside the ground truth; pick the citation if >1 resolved;
  answer §6's **three** sub-attestations when `missed_obligation` is among the modes — (a) the
  obligation applies to the fictional firm/activity, (b) the requested artifact is capable of
  violating it, (c) the judge's cited omission is material. **Any one `False` → the CLI refuses to
  offer `approve`.**
- **Output:** `data/cleared/` — tracked, and the deliverable.
- **This gate cannot be delegated to a subagent, a model, or a batch flag.** Goal: *human review
  IS the publication gate; there is no automated substitute.*

### R7.5 — **THE YIELD ESCALATION GATE — HARD STOP** 🛑
- **Trigger:** fewer than **~20 records** survive review.
- **Do:** **STOP. Report to the user.** State the true number, the `stop_reason`, the survivor
  breakdown by evidence mode, and the spend.
- **NEVER, under any circumstance:** loosen `candidate_cutoff_date`; admit `medium`/`low` impact;
  admit noisy `update_type`s; accept unresolvable citations; waive human review; weaken the failure
  bar; or synthesize/paraphrase records. Each is a named row in §6's anti-padding table, each is
  mechanically blocked, and **each block exists precisely because this moment is when someone would
  want to remove it.**
- **The correct outcome of a thin yield is a smaller set and an honest report.** Goal #11: *"A
  30-record set of proven baseline failures is a success; a 200-record set padded with records the
  baseline handles competently is a failure."* If fewer than ~20 survive, that is **the** condition
  the user asked to be woken for — the user decides, not the implementer.

---

# PHASE 8 — Vendor + generate

### P8.1 — Vendor the real cleared set
- **Do:** copy `prep/data/cleared/cleared_records.json` → `template/src/data/cleared-set.json`,
  replacing the synthetic fixture.
- **Verify:** `cd template && npx vitest run tests/schema.test.ts` — **every real record parses**
  against `ClearedRecordSchema`. This is the swap-safety mechanism Fact 2 promised; if it fails, the
  seam drifted and P8 stops here.

### P8.2 — Generate the scenario-locked constants
- **Command:** `prep/.venv/bin/python run_prep.py --emit-template-config`
- **Writes (as ordinary committed `template/` source):** `config.ts`'s `DEMO_TRIGGER_RECORD_ID`,
  `firmProfile.ts`'s `DEMO_FIRM_PROFILE`, `baselineAgent.ts`'s `SCENARIO_PERSONA_INSTRUCTIONS`,
  `scenario/prompts.ts` in full.
- **Raises rather than emits** if the winner has **no** `predicts_stage_a_violation` record (→ R7.5's
  sibling escalation) or if no candidate survives narrowing.
- **Also update — the named unskip obligation:** re-enable the `.skip`ped cases from **P6.2**
  (`config.test.ts`'s generated-constant cases) and **P6.5**
  (`test_demo_trigger_record_survives_narrowing`). They were skipped precisely because the
  generation step had not run; this is the task where it has.
- **Verify:** `cd template && npm run test:unit` — green **with nothing skipped**.

### P8.3 — Commit
- Work branch, meaningful message. **Never push.**

---

# PHASE 9 — Definition of Done: the 9 success criteria, one by one

Each criterion → the exact command or observation that proves it. Nothing here is "should work".

| # | Success criterion (goal) | Proof |
|---|---|---|
| **1** | Fresh clone of `template/`, only `OPENAI_API_KEY`: `npm install && npm run dev` serves Studio on `:4111`, no further setup | `git clone` the extracted `template/` to a **fresh directory**, `cp .env.example .env` + real key, `npm install && npm run dev`; `curl -sf localhost:4111 > /dev/null` exits 0. (`import "dotenv/config"` is what makes this true across `mastra dev`/`tsx`/`vitest` alike, rather than relying on each runner's undocumented `.env` handling.) |
| **2** | A scripted prompt makes the guarded agent produce a **visible tripwire block in Studio**, citing a real Carver obligation with a **resolvable** URL and a real compliance date | `npm run demo:prompt` → paste into Studio's `compareWorkflow` run form → set `requestContext.firmProfile` (schema-driven form) → Run. **Observe:** `guardedStep` tripwires in the graph; the trace names the matched record; the citation URL opens. |
| **3** | The same prompt against the unguarded baseline produces **visibly non-compliant output** | Same run: `draftStep`'s branch completes and its draft is delivered. `npm test`'s baseline unsafe-ship rate `>= 0.8` is the quantitative form. |
| **4** | The comparison workflow appears in Studio with **no Studio-specific code**, and one run executes **both** branches to completion — guarded blocked, baseline not. A tripwire must **never** abort the run | `npx vitest run tests/comparisonWorkflow.test.ts` — asserts `status === "success"` (**not** `"tripwire"`), `guarded.blocked === true`, `baseline.text` truthy. Plus the Studio graph showing both branches. |
| **5** | `npm run demo` emits a **self-contained** HTML report, opening with **no server and no network** | `npm run demo` → `output/demo-report.html`. **Disconnect the network**, open via `file://`. Both drafts side by side, the obligation, a clickable citation, the compliance date. `evals.test.ts::test("report has no external references")` is the mechanical form. |
| **6** | `npm test` prints a baseline-vs-guarded scoreboard with a **material, reproducible gap** | `cd template && npm test` (**~609 calls / ~$23**; worst case 1,260 — this **includes the guardrail's own verdict call**). Prints the pinned table: baseline unsafe-ship `>= 0.8` vs guarded `<= 0.1` over the **same** `partition.scored`; block rate `0.00` vs `~0.96`; catch `>= 0.9`; **benign-task pass rate `>= 0.9`** over the n=30 control. |
| **7** | Every record in `data/cleared/` carries recorded failure evidence **and** a human sign-off | `prep/.venv/bin/python run_prep.py --verify-cleared` → `validate_cleared_record` over every file; `test_schema.py::test_no_unreviewed_records_in_cleared_dir`. |
| **8** | Every citation URL in the cleared set resolves | `--verify-cleared` re-resolves each `citation.url` and requires `"resolves"`. (Validated at clearing time; §14 notes re-validation is not automated in v1 and the README says so.) |
| **9** | `template/` has **zero** references to `prep/`, `carver-showcase`, or anything else in this repo | `grep -rn "carver-showcase\|\.\./prep\|mastra_prep\|carver_showcase" template/` → **no hits**. Then the real proof: copy `template/` to `/tmp`, `npm install && npm run test:unit` → green. |

### P9.1 — Learnings
- **Do:** add the non-obvious findings to `docs/LESSONS.md` (repo convention). Candidates already
  known from the spec stage: the `probe → curate → probe` cycle and the `ast` guard; reservations
  leaking on failed calls; `runEvals` handing agent scorers a message array, not the generate
  result; OpenAI accepting but not enforcing `minimum`/`maximum`.
- **Do:** confirm the root README's Projects table row from P0.1 is still accurate.

---

## Stress scenarios (spec §14) — every one assigned to a task

§14 specifies eleven stress scenarios and a behavior for each. None may be dropped; this table is
the assignment, so a reader can check coverage without trusting that they are scattered somewhere
above.

| §14 scenario | Task | Test that proves it |
|---|---|---|
| Empty narrowing result | **P6.7** | `carverGuardrail.test.ts` — a firm profile matching zero records → `processOutputResult` returns the draft **unchanged**, no `abort()`, **no `auditWriter.write()`** (the audit log means "a violation occurred"; a narrowing miss is not one) |
| Tripwire in `.parallel()` | **P6.6** (stubs) + **P6.11** (live) | `tripwireContainment.test.ts::test_both_tripwire_forms_normalize_identically`; `comparisonWorkflow.test.ts` asserts `status === "success"`, never `"tripwire"` |
| Unresolvable citation URL | **P1.6**, **P2.3**, **P4.1** | `test_urls.py` (the tri-state); `test_scoring.py` (`citation_fabricated` only on 404/410; `citation_unverifiable` otherwise); §6 drops a record if **no** URL resolves |
| Garbage/absent ground-truth compliance date | **P2.3** | `test_scoring.py` — unparseable/empty ground truth → `DateScore.not_applicable`, `is_failure=False`; the record is **not** excluded from candidacy, the dimension simply contributes no evidence |
| Malformed judge JSON | **P2.2** (prep), **P6.7** (template) | `test_judge.py` — retry once, then all-`"uncertain"`, **never** `"violation"`; `carverGuardrail.test.ts::test_judge_parse_failure_passes_through` — fail-open to pass-through, no exception escapes |
| Zero probe survivors | **P5.1**, **R7.5** | `run_prep.py` prints *"0 records survived — see goal #11: ship nothing rather than pad"* and exits **0** (an honest empty result, not an error) |
| Survivors exist but none carries Stage-A evidence | **P3.1**, **P8.2** | `stage_a_survivor_counts` surfaces it at *decision* time; `test_generate_template_config.py::test_raises_when_no_stage_a_evidence` — raises, writes nothing |
| A cleared record ranks outside its own profile's top 5 (`crowdedOut`) | **P3.2**, **P6.9** | `test_trigger_skips_crowded_out_candidate`; `evals.test.ts::test_partition_is_disjoint_and_total` — reported as its own partition, never scored as a miss |
| Non-ASCII regulator names | **P1.9** | `test_schema.py` — a non-Latin regulator name round-trips (`ensure_ascii=False` throughout) |
| Duplicate records | **P1.4** | `test_candidates.py::test_duplicate_ids_deduped` — `filter_candidates` is the **sole** dedup layer; first occurrence in file order wins |
| A citation that dies between clearing and demo | **P6.13** | Out of scope for automated re-checking in v1 — no scheduled re-validation job. `template/README.md` states it as a known limitation (§14) |

## Risk / lever notes

**Cost levers, and what each actually does:**

| Lever | Effect | When to touch it |
|---|---|---|
| `probe_max_records` (400) | Linear on curation spend — the single biggest lever | Lower it for a shakeout. Raising it does **not** relax the filter, so it is safe — it just costs more |
| `scenario_trial_size` (30) | 2 arms × 3 calls each — ~$2.30 | Lower for a dry run only; below `scenario_trial_min` the trial returns no winner **by design** |
| `target_set_size` (200) | Early-stop: curation halts at the ceiling | May shrink freely; `load_settings()` **raises** above 200 (goal #11's ceiling) |
| `max_completion_tokens` (3,000/1,500/1,200) | Bounds the **reservation**, and the output half of real cost | Do not raise casually — it is the output term of every reservation |
| `total_spend_ceiling_usd` (120) | The hard wall | Lowering is always safe (stops earlier). Raising is a deliberate spend decision |

**Levers that are NOT levers** — mechanically blocked, and the block is the point:
`reasoning_effort` (code constant; `low` would weaken the baseline → more failures → bigger yield =
goal #9's named rigging mode), `candidate_cutoff_date` (derived from `MODEL_CUTOFF`),
`judge_confidence_floor` (≥0.7), `snapshot_date` (code constant), `price_*` (pinned floors).

**Known risks:**

| Risk | Resolution |
|---|---|
| **Tripwire propagates out of `.parallel()` and kills the run** (goal #8's KNOWN RISK) | Resolved **empirically in P6.6/P6.11**, early, with stubs then one live run — not assumed either way, not deferred to Phase 9 |
| Thin yield (<20 survivors) | **R7.5's hard stop.** Report; never pad |
| Winner has zero Stage-A evidence | Visible at *decision* time via `stage_a_survivor_counts`; `emit_template_config` raises in P8.2. A **user decision**, not an automatic scenario switch (§7's Goal issue) |
| A citation dies between clearing and demo | Out of scope for automated re-checking in v1; README states it (§14) |
| Real prompts render badly against real corpus prose | **R7.2's $1 dry run** — the cheapest place to find out |

---

## Spec issues found while planning

**None.** Every module, test, fixture, stress scenario and figure this plan schedules is stated in
the spec; where the plan looked like it needed a decision (the `.skip`/unskip of the
generated-constant tests; the dry-run cap), that is a *sequencing* choice this plan owns, not a
design change — the spec is silent on execution order by construction, which is what this stage is
for.

Two things carried forward as **planned constraints**, not defects:
- The spec's own accepted **Goal issue** — every vendored record is `impact_label == "high"`, so
  goal #6's `medium`/`low` branches are **dead code against real data**. No task exercises them
  live; `carverGuardrail.test.ts` covers them with synthetic fixtures (P6.7) and `template/README.md`
  states the limitation (P6.13).
- §7's **Goal issue** — goal #10's scenario rule does not guarantee the winner can support success
  criterion #2. Handled by reporting (`stage_a_survivor_counts`) and a loud raise (P8.2), never by
  silently re-ranking scenarios.
