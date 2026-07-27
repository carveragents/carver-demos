# Cost–Accuracy–Latency Experiment Plan (whitepaper v1.2 evidence)

**Status:** READY FOR EXECUTION — but Phase 1 ends in a HARD USER SIGN-OFF GATE. Do not run
Phase 3+ until the user has approved the question set and rubric keys.
**Author:** orchestrating session 2026-07-27. **Executor:** any capable agent with this repo.
**Worktree:** `/home/ubuntu/work/scribble/code/repos/carver-demos-docs-carver-whitepaper`
(branch `flux/docs-carver-whitepaper`). All paths below are relative to `mastra-studio-demo/`.

---

## 1. Objective

Produce, from ONE experiment set, measured data for three whitepaper upgrades:

1. **A cost-vs-accuracy frontier chart** for §3 — all three arms plotted with both axes from
   the *same runs* (today: dollars come from one benchmark, accuracy %s from another; that seam
   is the thing this experiment removes).
2. **E2E latency per question/arm** — reported as its own dimension (median + spread), never
   blended into accuracy or cost.
3. **Warm-cache replay economics for the Carver arm** — upgrades the whitepaper's
   "Projected — not yet measured" $22.57/1k box (`whitepaper/index.html` §06) to a measured number.

Plus a **measured breakeven**: (Carver cost/question − baseline cost/question) ÷ (baseline error
rate). Currently estimated at ~$0.16/flawed answer from mixed sources; this experiment makes it
one-source.

## 2. Prior art you must read first

- `docs/DEMO.md` — sections "Result 1/Result 2" (~line 900): the existing 3-scenario ×
  3-arm × 3-repeat suite, its findings (baseline 80% capped/uncited; web 100% but one silent
  5/5→3/5 drop; Carver 100% held), and the doctrine/hazards list (~line 948). The hazards are
  binding: `maxSteps=8` cap on every arm, naive demo prompts, token burn as counter-metric.
- `scripts/trigger-probe.mjs` — the harness to extend. Scenario shape: `{id, label, carver,
  system, user, checks[]}`. It already measures latency, tool calls, token usage, and runs
  mechanical checks. Carver arm = per-scenario agent name.
- `scripts/build-domain-index.mjs` — builds the per-domain Carver index a new scenario's agent
  needs. **Constraint: every question's domain must have a built index before its Carver arm can
  run.** Prefer domains where the corpus is strong (see
  `whitepaper/figures/whitepaper-data.json` → section1.sectors_by_taxonomy_top).
- `whitepaper/figures/whitepaper-data.json` — section3 has the rates table and the projected
  replay numbers this experiment will replace/confirm.
- `whitepaper/README.md` — the honesty-guards list. Nothing in this experiment may weaken them.

## 3. Definitions

**Arms (3):** `baseline` (memory only, no tools) · `web` (hosted web-search tool) · `carver`
(domain-index retrieval). Same model, same `maxSteps=8`, same system/user prompts per question.

**Dimensions measured per run:**

| Dimension | Source | Reported as |
|---|---|---|
| Accuracy | rubric checks (Phase 2) | % checks passed; must-pass gating; error-type taxonomy |
| $ cost | usage split × rates table | $/question and $/1k, fresh vs cached input priced separately |
| **E2E latency** | wall-clock ms, request start → final token | median + min–max band per question/arm |
| Reproducibility | spread across 3 repeats (accuracy AND latency AND tokens) | separate axis/error bars — never folded into accuracy |
| Replay cost (Carver + web only) | warm re-run pass (Phase 4c) | measured $/1k on repeat vs first run |

**Model:** record the exact model id the mastra app is configured with. If it is
`openai/gpt-5.6-sol`, use the rates already in `whitepaper-data.json` section3.rates
(input $5/M, cached $0.50/M, output $30/M, web search $0.01/call). If it is anything else,
look up current real rates, record them in the results file, and say so in your report.

## 4. Phase 0 — Preflight (30 min)

1. `npm install` if needed; `npm run dev`; wait for `:4111`; run
   `node scripts/trigger-probe.mjs crypto 1` as a smoke test. All 3 arms must return answers.
2. Confirm API keys present (never print or commit them).
3. Confirm which usage fields the SDK returns — specifically whether **cached input tokens**
   are reported separately (`cachedInputTokens` / `promptTokensDetails.cachedTokens` or
   similar). If the split is NOT available, say so immediately in your report and price all
   input at the fresh rate, labeled "cache split unavailable — cost is an upper bound."
4. Note git status; do all work on `flux/docs-carver-whitepaper`.

## 5. Phase 1 — Question set (author, then STOP for sign-off)

**25–30 questions**, each a realistic operator situation (system msg = signed-in operator
context; user msg = naive planning question naming NO rule, deadline, or regulator — same
pattern as existing scenarios). Strata:

- **Head, pre-cutoff (~8):** obligations knowable before the model's training cutoff
  (MiCA-class). Baseline should do well here — that's the point of the stratum.
- **Head, post-cutoff (~10):** obligations from corpus records dated after the model cutoff
  (check the model's cutoff; corpus has `reconciled_published_date`). This is where baseline
  should crater — the stratified split is a headline finding, so balance it carefully.
- **Tail, silent-trigger (~5):** an actor attribute (jurisdiction, decision method) fires an
  unnamed obligation — pattern of `scripts/state-lending-probe.mjs`. Plotted as separate
  points, NEVER pooled into head accuracy.
- **Reuse (~3–5):** the existing crypto/device/child-safety scenarios verbatim (free
  continuity with prior measurements) and, if usable, the state-lending scenario.

**Sourcing:** mine candidate obligations from the corpus snapshot
(`../carver-showcase/data` — READ-ONLY) in domains with strong coverage AND a buildable
domain index. For each question record the ground-truth corpus record id(s).

**Pre-registered keys:** for every question, write the answer keys (facts, citations, dates,
jurisdiction overlays, thresholds) from the ground-truth record BEFORE any arm runs. Commit
the question file BEFORE running arms — the commit timestamp is the pre-registration proof.

**Output:** `whitepaper/experiments/questions.json` — schema:

```json
{ "id": "q07", "stratum": "head-post-cutoff", "domain": "healthcare",
  "carver_agent": "<agent id>", "index_built": false,
  "ground_truth_record_ids": ["..."], "system": "...", "user": "...",
  "keys": { "...": "see Phase 2 rubric fields" } }
```

> **HARD GATE: present the full question list + keys to the user for approval before
> proceeding. Do not run Phase 3+ without it.** Curated/authored records rules apply: never
> fabricate or paraphrase corpus records; any hand-curated addition is REVIEW-REQUIRED.

## 6. Phase 2 — Rubric encoding

Per question, **6–8 checks**: 4 universal + 2–4 question-specific keyed facts.

**Universal:**
1. `cite-real` — cited statute/section/regulator exists and matches ground truth.
   **MUST-PASS** (fail ⇒ question scored 0 for that arm, error type `hallucination`).
   Judge-graded with corpus lookup.
2. `no-fabricated-obligation` — asserts no obligation that does not apply. **MUST-PASS**,
   error type `hallucination`. Judge-graded. (This is the precision side; the old 5-regex
   rubric measured only recall.)
3. `provenance` — includes a verifiable link/source. Regex (`https?://`). Baseline is
   expected to structurally fail this; that is a finding, not a bug.
4. `temporal-validity` — current version/amendment status where the key says it matters
   (e.g., "SB 24-205 as amended by SB 26-189"). Judge-graded; error type `stale`.

**Question-specific (from pre-registered keys):**
5. `controlling-obligation` — names the key obligation. Regex where possible. Error type `miss`.
6. `jurisdiction-overlay` — includes the applicable state/regional layer, where the key has
   one. Error type `miss` (the silent-trigger dimension, graded on head questions too).
7. `actionable` — the concrete action + deadline + recipient. Regex-able (dates, day counts).
8. `scope-boundary` — threshold/exemption where the key has one.
9. `penalty-accuracy` — IF the answer volunteers a penalty, it must be correct (checked only
   when volunteered — accuracy of what's said, not required content).
10. `useful` — did not hedge to uselessness ("consult counsel" with no substance passes nothing).

**Scoring:** accuracy = passed/total for that question, EXCEPT a must-pass failure caps the
question at 0. Report per-stratum means AND the pooled mean; report error-type counts
(`miss` / `hallucination` / `stale`) separately — never blended.

**Judge protocol:** LLM judge (capable model) with the pre-registered key in the judge prompt
and NO knowledge of which arm produced the answer (strip arm names, tool traces, and any
self-identification from the answer text before judging). Persist every judge verdict + one-line
rationale. Flag a random 10% of judge calls into `experiments/spot-check-queue.md` for human
review.

## 7. Phase 3 — Harness extension

Extend `scripts/trigger-probe.mjs` (or a sibling `scripts/frontier-probe.mjs` that imports its
machinery — prefer the sibling; do not destabilize the existing probe):

1. Load scenarios from `experiments/questions.json` instead of the inline array.
2. Persist RAW per-run records to `whitepaper/experiments/runs.jsonl`, one line per run:
   `{run_id, question_id, stratum, arm, repeat, model, started_at, latency_ms, tool_calls,
   usage: {fresh_input, cached_input, output, reasoning, total}, cost_usd, answer_text,
   error: null|string}`. **answer_text is mandatory** — grading and audit depend on it.
3. Compute `cost_usd` in-harness from the recorded rates (fresh vs cached priced separately;
   +$0.01/web-search call for the web arm — count the calls).
4. Latency = wall-clock from request send to final token, ms.
5. Build any missing domain indices first (`build-domain-index.mjs`); record build time and
   index size per domain in `experiments/index-build-log.md` (context for the report, not a
   per-question cost).

## 8. Phase 4 — Run protocol

- **(a) Main pass:** N questions × 3 arms × **3 repeats**. Interleave arms per question
  (q1: base, web, carver, base, web, carver…) rather than blocking by arm, so time-of-day
  drift spreads evenly. Sequential is fine; parallelize only if the mastra dev server stays
  stable under it.
- **(b) Failure handling:** on transport error, retry once; a second failure records
  `error` in runs.jsonl and moves on (report the count — no silent drops). NEVER edit a
  recorded run.
- **(c) Replay pass (the projected-→measured upgrade):** immediately after the main pass,
  re-run the IDENTICAL Carver-arm request for every question once more (repeat=4,
  `phase: "replay"`), close enough in time to hit provider prompt cache. Also re-run the web
  arm identically for 5 questions (sampled across strata). Compare cached_input share and
  $/question vs first runs. This measures the whitepaper's $22.57/1k projection and the
  "web cost does not decline on repetition" claim.
- **(d) Budget guard:** estimate ≈ 30q × 3 arms × 3 reps ≈ 270 runs + ~35 replay runs.
  Web arm dominates (~50k tok/run). Expected total **under $100**. If projected spend
  exceeds **$150**, STOP and ask the user.
- **(e) Wall-clock:** at ~45–140s/run, expect 4–8 h sequential. Run in background; checkpoint
  after every run (runs.jsonl is append-only, so the suite is resumable by skipping
  already-present run_ids).

## 9. Phase 5 — Grading

1. Regex checks: run mechanically over answer_text.
2. Judge checks: per §6 protocol, arm-blinded, verdicts to
   `whitepaper/experiments/grades.jsonl` (`{run_id, check_id, pass, error_type|null,
   judge_rationale}`).
3. Spot-check queue: write the 10% sample with answer excerpts to
   `experiments/spot-check-queue.md`; flag for the user, but don't block analysis on it —
   mark affected aggregates "pending spot-check" until reviewed.

## 10. Phase 6 — Analysis & outputs

Write `whitepaper/experiments/analysis.py` (or .mjs) that consumes runs.jsonl + grades.jsonl
and emits `whitepaper/figures/frontier-data.json`:

- Per arm × stratum: accuracy mean, $/question (median + IQR), $/1k, latency median + min–max,
  reproducibility (per-question repeat spread), error-type counts.
- Frontier points: (cost, accuracy) per arm, pooled AND per-stratum; state whether web is
  Pareto-dominated by Carver in these data (do not assume it will replicate).
- Breakeven: (carver − baseline) $/question ÷ baseline flawed-answer rate, with the flawed-rate
  definition stated (questions with ≥1 failed check ÷ questions).
- Replay: measured Carver warm $/1k vs first-run $/1k vs the projected 22.57; web replay delta.
- Every number the whitepaper will render must be in this JSON (single-source-of-truth
  doctrine, same as whitepaper-data.json).

**Report back (do not edit the whitepaper HTML — that is a separate, user-approved step):**
a summary with the frontier table, stratified accuracy, latency table, breakeven, replay
result vs projection, error-type counts, failed-run count, judge disagreement notes, and
anything that did NOT go as expected — negatives at equal volume.

## 11. Honesty guards (binding)

- Report negatives at equal volume; if an arm surprises (e.g., web wins a stratum, Carver
  drops below 100%), that goes in the report at full prominence.
- Latency: report as measured; do NOT convert into a "faster" marketing claim — prior
  measurements conflict (probe suite: Carver ~30% faster; Beat 4: wash) and the whitepaper
  currently carries a no-speed-claim guard. Reconciling them is a finding for the report.
- Web arm cost remains "a floor" (provider-side search tokens partially invisible).
- Fee asymmetry carries over: these are inference costs; no Carver fee is modeled.
- Accuracy claims are per this rubric — the report must characterize the rubric's limits
  (K checks/question, judge-graded fraction, spot-check status).
- No fabricated corpus records anywhere in questions or keys.
- Pre-registration: questions+keys committed before arms run (Phase 1 gate).

## 12. Acceptance criteria

1. questions.json committed BEFORE any main-pass run (verifiable in git history), user-approved.
2. runs.jsonl: ≥95% of planned runs completed; failures counted and reported.
3. Both axes of every frontier point derive from the same runs.
4. E2E latency reported per question/arm (median + spread).
5. Replay pass completed; projected-vs-measured comparison stated.
6. grades.jsonl complete; spot-check queue delivered; error taxonomy reported.
7. frontier-data.json is the single source for every reported number.
8. No existing file's honesty guard weakened; no whitepaper HTML edited.
