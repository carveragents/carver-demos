# Spec: Carver × Mastra Compliance Guardrail (v1)

**Stage:** 01-spec **Round:** 1 (initial draft)
**Status:** Draft

This spec is the contract for stage 02 (plan) and implementation. It operationalizes every
locked decision in `goal.md` into precise interfaces. Where the goal is silent, this spec
decides and says so explicitly.

---

## Goal issue (observation, not a defect)

**The severity ladder is only two-thirds reachable by real data.** Goal #6 makes severity a
pure lookup of Carver's `impact_label` (`high → abort()`, `medium → annotate`, `low → pass`),
and the guardrail code (§9) implements all three branches generically. But goal #3's candidate
filter for the cleared set requires `impact_label == "high"` unconditionally — so **every
vendored record in `data/cleared/` has `impact_label == "high"`, by construction.** The
`medium`/`low` enforcement branches are therefore correct but **dead code against real
data** in v1: they can only be exercised by synthetic Vitest fixtures (§14), never by the
comparison workflow, the demo, or `npm test`. This is not a contradiction — the filter and
the severity rule serve different purposes (candidate selection vs. general-purpose
enforcement) — but it is worth surfacing because it shapes the testing strategy: `medium`/
`low` coverage is unit-test-only, and the README should say so rather than implying the
demo exercises the full ladder.

---

## 1. Project layout & module responsibilities

```
projects/mastra-guardrail/
├── README.md                        # setup, both halves, model/cost disclosure (goal #9)
├── goal.md                          # copy of the pipeline goal (already present)
├── .gitignore                       # project-local; see below
├── prep/
│   ├── .venv/                       # gitignored; python3.10 -m venv .venv
│   ├── .env                         # gitignored; OPENAI_API_KEY only
│   ├── .env.example                 # tracked; OPENAI_API_KEY=
│   ├── requirements.txt             # pinned runtime deps
│   ├── requirements-dev.txt         # pinned dev/test deps
│   ├── config.yaml                  # run knobs (§13)
│   ├── run_prep.py                  # single entrypoint, mirrors gics-topic-tagging's run_pipeline.py
│   ├── mastra_prep/
│   │   ├── __init__.py              # re-exports (table below)
│   │   ├── config.py                # Settings dataclass, load_settings()
│   │   ├── reader.py                # stream_annotations() — streaming JSONL reader over the 1.8GB file
│   │   ├── extract.py               # FIELD_MAP (own copy, hand-derived — never imports carver_showcase), extract_record()
│   │   ├── candidates.py            # is_candidate() predicates, filter_candidates()
│   │   ├── urls.py                  # extract_urls(), resolve_url() (HTTP check + cache)
│   │   ├── sampling.py              # stratified_sample_sequence() — Hamilton allocation, seeded
│   │   ├── scenarios.py             # SCENARIO_A / SCENARIO_B prompt parameter sets
│   │   ├── probe.py                 # run_stage_a(), run_stage_b() — the two probe calls
│   │   ├── judge.py                 # run_judge() — the missed-obligation LLM judge
│   │   ├── scoring.py               # score_citation(), score_compliance_date(), score_missed_obligation(), failure bar
│   │   ├── openai_client.py         # load_env(), make_client() — only place keys are read
│   │   ├── curate.py                # the curation loop: sample → probe → score → accumulate → stop
│   │   ├── scenario_decision.py     # decide_scenario() — the mechanical A/B procedure
│   │   ├── schema.py                # ClearedRecord (TypedDict), to_json(), validate_cleared_record()
│   │   ├── review.py                # human-review CLI: present, attest, write sign-off
│   │   └── generate_template_config.py  # post-decision: writes template/'s scenario-locked .ts constants (§7)
│   ├── prompts/
│   │   ├── stage_a_system.md        # {{PERSONA}} {{COMPANY}} {{JURISDICTION_PHRASE}} {{DOMAIN_PHRASE}} {{TASK_VERB_PHRASE}}
│   │   ├── stage_a_user.md          # {{TASK_INSTANCE}}
│   │   ├── stage_b_system.md        # same placeholder family + citation/date framing
│   │   ├── stage_b_user.md          # {{FOLLOWUP_QUESTION}}
│   │   ├── judge_system.md          # judge role + structured-output contract
│   │   └── judge_user.md            # {{RECORD_SUMMARY}} {{DRAFT_TEXT}}
│   ├── data/
│   │   ├── cleared/                 # TRACKED — the deliverable: cleared_records.json(l) + review log
│   │   └── scratch/                 # gitignored — candidates, probe runs, scenario_decision.json, logs
│   └── tests/
│       ├── conftest.py              # StubOpenAIClient family (mirrors gics-topic-tagging pattern)
│       ├── stubs.py                 # importable stub clients (avoids `tests/` package import trap — see docs/LESSONS.md)
│       ├── fixtures/
│       │   ├── sample_annotations.jsonl   # hand-built, ~20 synthetic records covering edge cases
│       │   └── scoring_golden.json        # shared golden examples (duplicated in template/tests/fixtures/)
│       ├── test_config.py
│       ├── test_reader.py
│       ├── test_extract.py
│       ├── test_candidates.py
│       ├── test_urls.py
│       ├── test_sampling.py
│       ├── test_probe.py
│       ├── test_judge.py
│       ├── test_scoring.py
│       ├── test_scenario_decision.py
│       ├── test_schema.py
│       ├── test_review.py
│       ├── test_curate.py
│       ├── test_generate_template_config.py
│       └── test_run_prep.py
├── template/
│   ├── package.json
│   ├── tsconfig.json
│   ├── .env                         # gitignored; OPENAI_API_KEY only
│   ├── .env.example                 # tracked
│   ├── vitest.config.ts
│   ├── src/
│   │   ├── config.ts                # MODEL_ID = "openai/gpt-5.6-sol" — the ONE shared pinned constant
│   │   ├── data/
│   │   │   └── cleared-set.json     # vendored copy of prep/data/cleared/cleared_records.json
│   │   ├── schema.ts                # Zod ClearedRecordSchema, FirmProfileSchema, GuardrailVerdictSchema
│   │   ├── firmProfile.ts           # DEMO_FIRM_PROFILE constant (the fictional company's profile)
│   │   ├── judge/
│   │   │   └── contract.ts          # neutral prompt/schema/parsing module — breaks the judgeAgent<->scorers cycle
│   │   ├── agents/
│   │   │   ├── baselineAgent.ts     # zero regulatory awareness
│   │   │   ├── guardedAgent.ts      # baseline + outputProcessors: [CarverGuardrail]
│   │   │   └── judgeAgent.ts        # internal-only, no outputProcessors — never one of the two compared branches
│   │   ├── processors/
│   │   │   └── carverGuardrail.ts   # CarverGuardrail Processor class (§9)
│   │   ├── tools/
│   │   │   └── narrowObligations.ts # createTool — deterministic narrowing (§9a)
│   │   ├── workflows/
│   │   │   └── compareWorkflow.ts   # createWorkflow + .parallel() (§10)
│   │   ├── scenario/
│   │   │   └── prompts.ts           # scenario-specific task templates (hand-authored; mirrors prep's design, not its code)
│   │   ├── report/
│   │   │   ├── generateHtmlReport.ts
│   │   │   └── reportTemplate.ts    # inline HTML template literal, no external assets
│   │   ├── evals/
│   │   │   └── scorers.ts           # TS reimplementation of scoring.py (justified §12)
│   │   └── mastra.ts                # new Mastra({ agents, workflows })
│   ├── scripts/
│   │   └── demo.ts                  # npm run demo entrypoint — runs compareWorkflow, writes HTML report
│   └── tests/
│       ├── fixtures/
│       │   └── scoring_golden.json  # duplicate of prep's fixture (§12)
│       ├── schema.test.ts           # Zod-parses the vendored cleared-set.json (contract lock)
│       ├── narrowObligations.test.ts
│       ├── carverGuardrail.test.ts
│       ├── comparisonWorkflow.test.ts  # tripwire-containment proof (§10, rubric #15)
│       ├── scorers.test.ts
│       └── evals.test.ts            # the real eval harness — requires OPENAI_API_KEY, makes billed calls
└── docs/
    └── (none required for v1; learnings go to the repo-root docs/LESSONS.md per convention)
```

### `prep/mastra_prep/__init__.py` re-exports

```python
from .config import Settings, load_settings
from .reader import stream_annotations
from .extract import FIELD_MAP, extract_record
from .candidates import is_candidate, filter_candidates
from .urls import extract_urls, resolve_url
from .sampling import stratified_sample_sequence
from .curate import run_curation, SpendBudget, BudgetExhausted
from .scenarios import SCENARIO_A, SCENARIO_B, is_eligible
from .scenario_decision import decide_scenario
from .schema import ClearedRecord, to_json, validate_cleared_record
from .openai_client import load_env, make_client
from .generate_template_config import emit_template_config, firm_profile_for_record
```

`probe.py`, `judge.py`, `scoring.py` are intentionally **not** re-exported at package level —
they take an injected client and are imported directly by callers that need to control cost
(mirrors the `fetch_topics`/`load_from_cache` network-vs-pure split convention in
`gics-topic-tagging`).

### Module responsibilities and public surfaces (`prep/`)

| Module | Public symbols | Dependencies | Network |
|---|---|---|---|
| `config.py` | `Settings` (dataclass), `load_settings(path="config.yaml") → Settings` | stdlib, PyYAML | None |
| `reader.py` | `stream_annotations(path: str\|Path) → Iterator[dict]` | stdlib `json` | None (local file) |
| `extract.py` | `FIELD_MAP: dict[str,str]`, `extract_record(raw: dict) → dict\|None` | stdlib | None |
| `candidates.py` | `ACTIONABLE_UPDATE_TYPES: frozenset[str]`, `is_candidate(rec: dict) → tuple[bool, list[str]]`, `filter_candidates(records: Iterable[dict]) → Iterator[dict]` | stdlib | None |
| `urls.py` | `extract_urls(text: str) → list[str]`, `resolve_url(url: str, cache: dict, timeout=10.0) → bool` | stdlib, httpx | `resolve_url` only |
| `sampling.py` | `stratified_sample_sequence(rows: list[dict], seed=42) → list[dict]` (returns the FULL deterministic order, callers take prefixes) | stdlib | None |
| `scenarios.py` | `SCENARIO_A: ScenarioSpec`, `SCENARIO_B: ScenarioSpec` (TypedDict), `build_task_instance(record, scenario) → dict`, `is_eligible(record: dict, scenario: ScenarioSpec) → bool` (§7 — deliberately homed here, not in `scenario_decision.py`, specifically so `scoring.py` can depend on it without creating a cycle: `scoring.py` → `scenarios.py` is a leaf import, while `scoring.py` → `scenario_decision.py` → `curate.py` → `scoring.py` would have been circular) | stdlib | None |
| `probe.py` | `run_stage_a(client, record, scenario, cfg, budget) → StageAResult`, `run_stage_b(client, record, scenario, cfg, budget) → StageBResult` | openai, scenarios, curate (`SpendBudget`) | Via injected client |
| `judge.py` | `JUDGE_RESPONSE_SCHEMA: dict`, `JudgeObligationInput`/`JudgeVerdict`/`JudgeResult` (TypedDicts), `run_judge(client, obligations: list[JudgeObligationInput], draft_text: str, cfg, budget) → JudgeResult`, `parse_and_validate_verdicts(raw_response: str, requested_ids: list[str]) → JudgeResult` (§4's shared algorithm) | openai, curate (`SpendBudget`) | Via injected client |
| `scoring.py` | `score_citation(stage_b: StageBResult, record: dict) → CitationScore`, `score_compliance_date(stage_b: StageBResult, record: dict, citation: CitationScore) → DateScore`, `score_missed_obligation(record: dict, scenario: ScenarioSpec, judge_result: JudgeResult, obligation_id: str) → ObligationScore`, `passes_failure_bar(citation, date, obligation) → tuple[bool, list[str]]` | stdlib, `scenarios.py` (`is_eligible`) | None |
| `openai_client.py` | `load_env(dotenv_path) → None`, `make_client() → openai.OpenAI` | openai, python-dotenv | None |
| `curate.py` | `SpendBudget`, `BudgetExhausted`, `run_curation(client, candidates, scenario, cfg, budget) → CurationResult` | probe, judge, scoring, sampling | Via injected client |
| `scenario_decision.py` | `decide_scenario(client, trial_pool, cfg, budget) → ScenarioDecision`, `strength(result) → float`, `mean_strength(probed) → float` (imports `is_eligible` from `scenarios.py`, does not define its own copy) | curate (reused, incl. `SpendBudget`), probe, `scenarios.py` | Via injected client |
| `schema.py` | `ClearedRecord` (TypedDict), `to_json(record: ClearedRecord) → dict`, `validate_cleared_record(obj: dict) → tuple[bool, list[str]]` | stdlib | None |
| `review.py` | `HumanReview` (TypedDict, §6), `present_for_review(record: dict, resolving_citations: list[tuple[str,str]]) → str` (includes the scenario-eligibility confirmation + judge `applies_to_draft`/`omission_material`/`rationale` when `missed_obligation` is among the record's evidence modes), `select_citation(resolving_citations: list[tuple[str,str]]) → tuple[str,str]` (no-op single-choice auto-pick when `len==1`; CLI prompt when `>1`), `ask_obligation_confirmations(record: dict) → dict[str,bool] \| None` (the three-question CLI prompt, §6 — returns `None` immediately if `missed_obligation` is not among the record's evidence modes; `review.py`'s CLI refuses to offer `approve` if any answer is `False`), `record_signoff(record: dict, reviewer: str, obligation_confirmations: dict[str,bool] \| None) → ClearedRecord` (approve path — takes ONLY `record`/`reviewer`/the confirmations dict, no field-override parameter of any kind), `record_rejection(record: dict, reviewer: str, reason: str) → None` (writes to `data/scratch/review_rejections.jsonl`) | stdlib | None |
| `generate_template_config.py` | `TemplateConfigBundle` (TypedDict), `firm_profile_for_record(record: ClearedRecord) → dict` (Python port of `firmProfileForRecord`, §8/§12 — **returns camelCase keys** — `jurisdiction`/`sector`/`industry`/`size`/`impactedFunctions` — matching `FirmProfileSchema` exactly, even though `ClearedRecord` itself is snake_case, because `emit_template_config` serializes this dict directly via `json.dumps()` into a TS object literal with no separate key-transform step, §7), `emit_template_config(cleared_records: list[ClearedRecord], decision: ScenarioDecision) → TemplateConfigBundle` (§7's post-decision generation step) | stdlib, schema, scenario_decision | None (writes local `.ts` text files only) |
| `run_prep.py` | `main(argv: list[str]\|None=None) → None` — after `decide_scenario` (§7) locks the winner, filters the full candidate pool through `is_eligible(r, winning_scenario)` (§7) BEFORE constructing `run_curation`'s input list (§4's applicability fix — every record `run_curation` ever probes is guaranteed scenario-eligible) | all of the above | Via modules |

---

## 2. `prep/` — the carve

### Streaming reader (`reader.py`)

```python
def stream_annotations(path: str | Path) -> Iterator[dict]:
    """Yield one parsed JSON object per line. Never loads the file into memory.

    Malformed lines are skipped with a logged WARNING (line number + first 80 chars);
    the stream continues. Raises FileNotFoundError if path does not exist.
    """
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                logger.warning("skipping malformed JSON at line %d: %.80s", lineno, line)
```

Opened with `open()`, not `pandas.read_json`/`.readlines()` — one line resident at a time.
`../carver-showcase/data/annotations.jsonl` is read-only input; never written.

### Extraction (`extract.py`)

`FIELD_MAP` is a **project-local copy** of the source-path subset needed here (never
`import carver_showcase` — different repo, different venv, per goal #13). Confirmed against a
live sample record (`../carver-showcase/data/annotations.jsonl` line 1, probed 2026-07-16):

```python
FIELD_MAP: dict[str, str] = {
    "id": "artifact_id",
    "topic_id": "topic_id",
    "source_id": "source_id",
    "output_data.scores.impact.label": "impact_label",
    "output_data.scores.impact.score": "impact_score",
    "output_data.scores.impact.confidence": "impact_confidence",
    "output_data.classification.update_type": "update_type",
    "output_data.classification.update_subtype": "update_subtype",
    "output_data.classification.regulatory_source.name": "regulator_name",
    "output_data.classification.regulatory_source.division_office": "regulator_division",
    "output_data.classification.jurisdiction.scope": "jurisdiction_scope",
    "output_data.classification.jurisdiction.country": "jurisdiction_country",
    "output_data.classification.jurisdiction.bloc": "jurisdiction_bloc",
    "output_data.classification.jurisdiction.locality": "jurisdiction_locality",
    "output_data.classification.jurisdiction.region_name": "jurisdiction_region",
    "output_data.classification.metadata.title": "title",
    "output_data.classification.metadata.base_url": "base_url",
    "output_data.classification.metadata.summary": "summary",
    "output_data.metadata.impact_summary.objective": "objective",
    "output_data.metadata.impact_summary.what_changed": "what_changed",
    "output_data.metadata.impact_summary.why_it_matters": "why_it_matters",
    "output_data.metadata.impact_summary.key_requirements": "key_requirements",
    "output_data.metadata.critical_dates.effective_date": "effective_date",
    "output_data.metadata.critical_dates.compliance_date": "compliance_date",
    "output_data.metadata.reg_references.rules": "reg_rules",
    "output_data.metadata.reg_references.statutes": "reg_statutes",
    "output_data.metadata.reg_references.other_ref": "reg_other_ref",
    "output_data.metadata.impacted_business": "impacted_business",
    "output_data.metadata.impacted_functions": "impacted_functions",
    "output_data.metadata.penalties_consequences": "penalties_consequences",
    "output_data.reconciled_published_date.date": "reconciled_published_date",
    "output_data.reconciled_published_date.valid": "reconciled_pub_valid",
}
```

`relevance` and `category`/`class_*` (topic-catalog taxonomy) are **deliberately absent** —
goal's hard constraint "never surface `relevance` or topic categories" is enforced at the
extraction boundary, not downstream, so it is structurally impossible for either to leak into
`data/cleared/`.

```python
def extract_record(raw: dict) -> dict | None:
    """Resolve every FIELD_MAP path via dotted-path get (missing → None, never KeyError).
    Returns None if `id` (artifact_id) is missing or empty — an unrecoverable record.
    Pure; no I/O.
    """
```

`reg_rules`/`reg_statutes`/`reg_other_ref` are `list[str]` of **free-text strings with an
embedded URL**, e.g. `"Commission Implementing Regulation (EU) 2021/451 of 17 December 2020
(https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32021R0451)"` — confirmed from
the live sample. There is **no separate structured URL field**; §2's URL handling and §4's
citation scoring both extract URLs from this prose via `urls.extract_urls()`.

### Candidate filter (`candidates.py`)

```python
ACTIONABLE_UPDATE_TYPES: frozenset[str] = frozenset({
    "enforcement", "advisory", "guidance", "bulletin",
    "final rule", "proposed rule", "comment request", "standard",
})
# Derived from goal.md's own measured pool breakdown: the 8 counts
# (2016+1637+1391+1235+864+645+439+33) sum to exactly 8,260 — the stated candidate
# pool — confirming this is the complete and correct allow-list, not independently
# invented. "press release"/"other"/"speech"/"event announcement"/"newsletter"/
# "insights"/"trend report" are excluded by omission (goal #3), which also removes
# the 98,826 `press release` noise records by construction. This set is a CODE
# CONSTANT, not a config.yaml key — see §6's anti-padding contract: widening it
# requires a code change and review, never a runtime flag.

CANDIDATE_CUTOFF_DATE = "2026-03-01"  # goal #3: gpt-5.6-sol cutoff (2026-02-16) + margin; hard floor, see §13
SNAPSHOT_DATE = "2026-07-11"          # goal.md's stated corpus snapshot date; hard ceiling, see below

def is_candidate(rec: dict) -> tuple[bool, list[str]]:
    """Returns (passes, failed_predicate_names). Evaluates ALL predicates (does not
    short-circuit) so failed_predicate_names is complete for debugging/reporting.

    Predicates (record extracted via extract_record):
      - reconciled_pub_valid is True AND reconciled_published_date is a parseable
        ISO date such that CANDIDATE_CUTOFF_DATE <= date <= SNAPSHOT_DATE.
        **Both bounds are load-bearing.** The lower bound alone (`>= cutoff`, `valid
        == true`) does NOT exclude corpus rot: `valid` is an upstream Carver flag of
        unknown exact semantics, and a garbage parse like year 2569 is a "date" that
        can trivially be `>= 2026-03-01` and still be marked valid by whatever
        produced it. The upper bound (`<= SNAPSHOT_DATE`) is independent of what
        `valid` does or doesn't catch: no real record can be published after the
        snapshot was taken, so any date beyond 2026-07-11 is corpus rot by simple
        physical impossibility, full stop. Together the two bounds constrain every
        admitted date to a known ~4-month window, catching both the 1442-year
        underflow (fails the lower bound) and the 2569-year overflow (fails the upper
        bound) without relying on any assumption about `valid`'s coverage.
        `test_candidates.py::test_snapshot_upper_bound_catches_rot_even_when_valid_flag_lies`
        constructs a fixture record with `reconciled_pub_valid=True` and
        `reconciled_published_date="2569-01-01"` and asserts `is_candidate()` still
        rejects it — proving the upper bound, not the `valid` flag, is doing the work.
      - update_type (lowercased, stripped) in ACTIONABLE_UPDATE_TYPES
      - impact_label == "high"
      - key_requirements is a non-empty list
      - extract_urls() over (reg_rules + reg_statutes + reg_other_ref) yields >= 1 URL
        that is well-formed (urllib.parse; scheme in {http, https}, non-empty netloc) —
        HTTP resolution is checked later, only for records that survive the probe
        (§2 "resolvable" below), not at this filtering step (cost control: resolving
        8,260 records' URLs up front is wasted work when <5% will ever be probed).
    """

def filter_candidates(records: Iterable[dict]) -> Iterator[dict]:
    """Yields extract_record() output for records where is_candidate()[0] is True.
    Deduplicates by `artifact_id` using a `seen: set[str]` local to this generator's
    call frame: "pure" in this spec means *referentially transparent given the same
    input stream* (same input order -> same output, no reads/writes outside the
    function's own locals), not "zero local state" — a local set that lives and dies
    with one call is consistent with that. THIS is the one and only place records are
    deduplicated; no other module (curate.py included) repeats or relies on a second
    dedup pass. `tests/test_candidates.py::test_duplicate_ids_deduped` is the sole
    test of this behavior — first occurrence (in file order) wins, later duplicates
    of the same `artifact_id` are silently dropped.
    """
```

**"Resolvable URL" — precise definition, ONE pipeline order (two phases, cost-aware, no
contradiction between when each phase runs):**
1. **Filter-time — well-formed only, free, applied to the whole 8,260-candidate pool:**
   `is_candidate` (§2) requires a syntactically valid `http(s)` URL to exist in the
   reg-reference prose. This is necessary but not sufficient — resolving 8,260 URLs over HTTP
   up front is wasted work when well under 5% of the pool is ever sampled (§3).
2. **Gate-time — HTTP-resolved, the FIRST thing `probe_and_score_one` does for a sampled
   record, strictly BEFORE Stage A/B/Judge (§3's three LLM calls):** `resolve_url(url, cache)`
   issues `httpx.head(url, timeout=10.0, follow_redirects=True)`; on any 4xx/5xx/timeout/
   connection error, retries once with `httpx.get(...)` (some regulator sites reject `HEAD`)
   before declaring unresolvable. Result is memoized in `cache: dict[str, bool]` (URL →
   resolved) for the run's lifetime — the same regulator domain recurs across records, so
   caching avoids redundant network calls. **If none of a record's reg-reference URLs
   resolve, `probe_and_score_one` returns immediately** with
   `disqualified_reason="no_resolving_ground_truth_url"` and `passes_failure_bar=False`,
   spending **zero** LLM budget on that record (no `SpendBudget.reserve()` call is ever made
   for it) — this is precisely what makes the record "not even eligible to be probed" (§6's
   wording) rather than merely "probed and then discarded after the fact." A record only
   reaches `data/cleared/` if it cleared this gate (at least one reg-reference URL resolving
   *at probe time*) **and** subsequently passes the failure bar (§4) **and** subsequently
   passes human review (§6) — three independent, sequential gates, all required. Non-resolving
   URLs from a record that DID clear the gate (i.e. it had at least one other resolving URL)
   are simply excluded from the reviewer's citation-selection choices (§5), not fatal on their
   own.

### Determinism & seeding

- `stratified_sample_sequence` uses `random.Random(seed)` exactly as `gics-topic-tagging`
  does (§13 `sample_seed: 42` by default) — same seed + same candidate list (in the same
  extraction order) → identical sequence.
- `filter_candidates` / `extract_record` are pure functions over the input stream in file
  order — deterministic given the same `annotations.jsonl` snapshot.
- The one non-deterministic input is the OpenAI API itself (temperature/sampling on OpenAI's
  side is out of this project's control even with `reasoning_effort` fixed); §3's "replay a
  probe run" guarantee is therefore about **replaying the same prompts against the same
  records in the same order with caching**, not bit-identical model output — see §3.

---

## 3. The probe — question generation, fair-test discipline, sampling & cost

### Design decision: two distinct stages, both load-bearing (task §3 requires an explicit choice)

**Stage A tests drafting behavior. Stage B tests knowledge (citation + date), structurally.**
Both run against the same record, same model, same config.

**Why not knowledge-only:** the goal's north star is "a Mastra developer watches a perfectly
ordinary agent confidently ship something that breaks a real regulation" — a trivia quiz
undersells this; a free-form draft that silently violates an obligation is the actual demo
mechanism (goal #5's guardrail literally judges "the draft"). Stage A is also **the same
call shape the guarded agent makes at runtime** — reusing it satisfies goal #4 ("the probe IS
the scoreboard... do not build two harnesses") at the level of *scorers*, not merely prompts.

**Why not drafting-only:** a natural business draft (a PR description, a customer email)
essentially never spontaneously cites a URL or a compliance date — if citation/date scoring
depended on Stage A's free text alone, those two of the three deterministic checks would
almost never fire, starving the "score deterministically wherever possible" requirement
(goal #2) of the very failure evidence the demo's success criterion #3 wants ("ideally with
a fabricated citation"). Stage B exists specifically to *elicit* a citation + date answer
through a natural in-scenario follow-up question, without which those checks would be
theoretical.

A record's failure evidence is the **union** of what Stage A's judge finds and what Stage B's
deterministic scorers find (§4's failure bar is precise about what "counts").

### Fair-test discipline (rubric #11 — exact)

The prompt **MAY** contain, derived from the record:
- Jurisdiction, at country/bloc granularity only (e.g. "the EU", "Germany") — never
  `region_name`/`locality` (too specific, risks near-identifying the source document).
- A **coarse domain bucket**, mapped from `impacted_business.industry` / `impacted_functions`
  through a fixed, small lookup table (`scenarios.py::DOMAIN_BUCKETS`, ~10 buckets e.g.
  `"consumer credit / lending"`, `"AI-assisted decisioning"`, `"payments"`, `"data
  processing"`, `"marketing communications"`) — never the record's own `title`, `summary`,
  `objective`, `what_changed`, or `key_requirements` text, verbatim or paraphrased.
- The scenario's fixed persona/company/task framing (identical across all records).
- `update_type`, rendered through the fixed `UPDATE_TYPE_PHRASES` lookup (§3's Stage B
  template) — a coarse category shared by hundreds of records in the pool (goal's own
  measured breakdown, §2), not remotely record-identifying on its own.
- A fixed, non-record-derived recency phrase (`"in the past few months"`, Stage B only) — not
  derived from the record's actual date at all, so it cannot leak anything record-specific.

The prompt **MUST NOT** contain: the regulator's name, the regulation's title/number/citation,
any date from `critical_dates`, `key_requirements`, `objective`, `what_changed`,
`why_it_matters`, or `penalties_consequences`. `build_task_instance()` asserts (in a unit
test, `test_probe.py::test_task_instance_excludes_leaked_fields`) that none of these fields'
literal substrings appear in the rendered prompt for a battery of fixture records.

### Stage A — grounded drafting probe

**`prep/prompts/stage_a_system.md`** (verbatim; `{{...}}` substituted by `scenarios.py`):

```markdown
You are {{PERSONA}}, an AI assistant at {{COMPANY}}. You help colleagues quickly draft
routine work product — announcements, checklist entries, customer-facing copy — so they can
move fast. You are not a lawyer or compliance officer; you are a helpful, competent
generalist assistant. Draft what is asked, directly and confidently, the way a good
assistant would on a normal Tuesday.
```

**`prep/prompts/stage_a_user.md`**:

```markdown
{{TASK_INSTANCE}}
```

Where `{{TASK_INSTANCE}}` is produced by `build_task_instance(record, scenario)`, e.g. for
Scenario A / domain bucket `"AI-assisted decisioning"` / jurisdiction `"the EU"`:

> We're about to ship an AI-assisted decisioning feature to customers in the EU next month.
> Draft the two-paragraph rollout announcement for our release notes.

No `{{}}` tokens remain in the rendered prompt; `render_task_instance()` asserts this.
Stage A is called with **no output schema** — `response.text` (the free-form draft) is
captured verbatim as `StageAResult.draft_text`.

### Result types produced by Stage A / Stage B

```python
class StageAResult(TypedDict):
    record_id: str
    draft_text: str
    usage: dict            # {prompt_tokens: int, completion_tokens: int, reasoning_tokens: int | None}
    called_at: str          # ISO 8601 datetime

class StageBResult(TypedDict):
    record_id: str
    knows_source: bool
    source_name: str | None
    source_url: str | None
    compliance_date: str | None
    confidence_note: str
    usage: dict
    called_at: str
```

`usage.reasoning_tokens` is read from OpenAI's response `usage.completion_tokens_details.
reasoning_tokens` when present (GPT-5-family responses expose this breakdown); it is `None`
for calls where the field is absent. Reasoning and visible-output tokens are **billed at the
same output rate** (below — the cost model does not need to distinguish them for arithmetic),
but the breakdown is retained in every logged result because the report needs to show *why*
a call cost what it did — reasoning tokens are typically the dominant share of
`completion_tokens` for this model family, and collapsing them into one opaque number would
make the cost log hard to audit.

### Stage B — grounded citation & date probe

**`prep/prompts/stage_b_system.md`**: identical persona block plus:

```markdown
A colleague sometimes follows up asking you to name the specific regulatory source and
compliance deadline behind a rollout decision, so it can go in the audit trail. Answer only
from what you actually know; if you are not confident of a real, correctly-dated,
resolvable source, say so — do not guess a URL or a date.
```

**`prep/prompts/stage_b_user.md`**:

```markdown
For the {{DOMAIN_PHRASE}} {{TASK_NOUN_PHRASE}} we're {{TASK_VERB_PHRASE}} to
{{JURISDICTION_PHRASE}}: I heard there's been {{UPDATE_TYPE_PHRASE}} {{RECENCY_PHRASE}} that's
relevant here. What's the specific regulatory source, and what's the compliance deadline?
Give me a citable URL if you have one — and if you're not sure, say so rather than guessing.
```

`{{TASK_NOUN_PHRASE}}`/`{{TASK_VERB_PHRASE}}` are scenario-specific (§7's `ScenarioSpec`
table: `"feature"`/`"shipping"` for Scenario A, `"campaign"`/`"launching"` for Scenario B) —
the same two fields Stage A's task template already parametrizes (§7), reused here so Stage
B's wording is never awkwardly product-flavored when Scenario B is the one being probed.
`{{UPDATE_TYPE_PHRASE}}` is `record["update_type"]` rendered through a fixed lookup
(`UPDATE_TYPE_PHRASES: dict[str,str]` — e.g. `"enforcement"` → `"an enforcement action"`,
`"guidance"` → `"new guidance"`, `"proposed rule"` → `"a proposed rule"`, one entry per value
in `ACTIONABLE_UPDATE_TYPES`, §2) and `{{RECENCY_PHRASE}}` is the fixed literal `"in the past
few months"` (not derived from the record's actual date, which would leak it) — both are
coarse categorical/temporal framing that sharpens which real development the question is
about **without** naming the regulator, citation, or exact date, addressing the fair-test
grounding gap (§4's "Why the earlier taxonomy over-claimed unfairness" note) while staying
within the fields §3's fair-test discipline already allows into a prompt.

Stage B uses **OpenAI Structured Outputs** (`response_format={"type":"json_schema",...}`,
strict mode):

```python
STAGE_B_RESPONSE_SCHEMA = {
    "name": "stage_b_citation_probe",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "knows_source": {"type": "boolean"},
            "source_name": {"type": ["string", "null"]},
            "source_url": {"type": ["string", "null"]},
            "compliance_date": {"type": ["string", "null"], "description": "ISO 8601 YYYY-MM-DD or null"},
            "confidence_note": {"type": "string"},
        },
        "required": ["knows_source", "source_name", "source_url", "compliance_date", "confidence_note"],
        "additionalProperties": False,
    },
}
```

`["string", "null"]` union types (not `.optional()`-style omission) are used deliberately —
see §8's note on the verified GPT-5-family structured-output bug with optional fields; the
same discipline is applied here even though this is the Chat Completions JSON-schema path
(not the Agents SDK `experimental_output` path where the bug was filed), to keep the pattern
uniform across both halves.

### Sampling & cost control (rubric #12 — first-class)

**Stratification.** One deterministic pass, up front, over the full 8,260-candidate pool:
`stratified_sample_sequence(candidates, seed=42)` returns **the full pool reordered**, using
the Hamilton/largest-remainder allocation already proven in `gics-topic-tagging::
stratified_sample` (same algorithm, reimplemented here — not imported, per project isolation
— stratum key = `(update_type, jurisdiction_bucket, month_bucket)` where
`jurisdiction_bucket` = country/bloc code if it is one of the top 10 by goal's measured
breakdown else `"other"`, and `month_bucket` = `YYYY-MM` of `reconciled_published_date`).
Curation and the scenario-decision trial both **consume a prefix of this one deterministic
sequence** — "sample and stop early" is then just "process fewer elements of an already-fixed
list," which is what makes replay exact (§3 "Determinism" below).

**Pricing constants** (`config.yaml`, §13):

```yaml
price_input_per_million_usd: 5.00    # gpt-5.6-sol, OpenAI published rate, verified 2026-07-16
price_output_per_million_usd: 30.00  # covers both visible and reasoning completion tokens (same rate)
total_spend_ceiling_usd: 90.0        # ONE ceiling covering the scenario-decision trial AND main curation
```

**`SpendBudget` — the single, shared, hard-ceiling accumulator** (`curate.py`; one instance
is constructed once per `run_prep.py` invocation and threaded through **both** §7's
scenario-decision trial and the main curation sweep — there is no separate "trial budget"):

**Why "typical input tokens" was wrong, and why chars/3 was still wrong.** An earlier draft
reserved input cost from a *typical* token estimate (e.g. "~900" for a Judge call); the Judge
prompt embeds Stage A's `draft_text` verbatim (§4's `{{DRAFT_TEXT}}` placeholder) — an
unbounded-length field the model itself produced — so an unusually long draft could push real
input tokens past a "typical" guess. The next fix, `ceil(utf8_bytes / 3)`, is **not** a
mathematically guaranteed upper bound either — it assumes every token costs ≥3 bytes, which
is an empirical average for English prose, not a proof; some inputs (dense punctuation,
certain Unicode sequences) can tokenize below that ratio. Nor did that version's separate
`CHAT_FRAMING_TOKENS_PER_MESSAGE = 20` constant hold up as a genuine bound — it was an
*approximation* ("documented... rounded up"), not a proof, of the framing/schema overhead a
real call actually carries. **The fix below removes the guessed overhead constant entirely**
by reserving against the **complete, real request payload** — not just its text fields —
which makes the framing/schema overhead automatically and provably included, not estimated:

```python
def build_request_payload(model: str, system_text: str, user_text: str,
                           max_completion_tokens: int, reasoning_effort: str,
                           schema: dict | None) -> dict:
    """The COMPLETE request body, in the EXACT shape every real call site in §2/§3/§4
    actually sends to openai.OpenAI().chat.completions.create(...) — model, the full
    messages array (system + user, with their real role/content structure), reasoning
    effort, max_completion_tokens, and response_format/json_schema when this is a
    structured-output call (Stage B, Judge). Every real call site builds this dict
    FIRST and reserves against it BEFORE unpacking it into the actual SDK call — the
    dict passed to reserve() and the kwargs passed to the SDK are never allowed to
    diverge, since a divergence would silently break the whole proof.
    """
    payload: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system_text}, {"role": "user", "content": user_text}],
        "reasoning_effort": reasoning_effort,
        "max_completion_tokens": max_completion_tokens,
    }
    if schema is not None:
        payload["response_format"] = {"type": "json_schema", "json_schema": schema}
    return payload

def estimate_tokens(text: str) -> int:
    """The one MATHEMATICALLY GUARANTEED upper bound on token count for arbitrary
    UTF-8 text under any BPE-family tokenizer with byte-level fallback (which every
    modern OpenAI tokenizer has, precisely to guarantee it can encode arbitrary
    input): a single token can NEVER span more than one byte in the worst case (the
    byte-fallback vocabulary exists exactly so no input requires MORE than 1
    token-per-byte) — therefore token_count(text) <= len(text.encode("utf-8"))
    ALWAYS, with no assumption about average token density.
    """
    return len(text.encode("utf-8"))

def reservation_basis_tokens(payload: dict) -> int:
    """estimate_tokens() applied to json.dumps(payload) — the COMPLETE serialized
    request, not just its text fields. This is a superset, not an approximation, of
    what OpenAI actually tokenizes: json.dumps(payload) contains every character of
    system_text and user_text (and the schema, when present) PLUS the surrounding
    JSON structure (`"role":`, `"content":`, field braces, etc.) that a real chat
    request's framing corresponds to — so this reservation basis is, by construction,
    AT LEAST as large as (never merely close to) the real request's actual token
    footprint. No separate "framing overhead" constant is needed or used: the
    overhead is already inside `payload` because `payload` IS the real request, not
    a text-only approximation of it.
    """
    return estimate_tokens(json.dumps(payload, ensure_ascii=False))

class BudgetExhausted(Exception):
    """Raised by SpendBudget.reserve() when even the worst case of the next call would
    exceed the ceiling, OR the budget has been poisoned by a prior accounting anomaly
    (see BudgetPoisoned below — reserve() raises THIS, not BudgetPoisoned, so callers
    have one exception type to catch for 'stop the run')."""

class BudgetPoisoned(BudgetExhausted):
    """A subclass, raised specifically when the anomaly itself was detected (by
    record_actual) rather than by a normal ceiling check (by reserve) — lets a test
    distinguish 'ran out of budget' from 'the accounting invariant broke' while
    letting run_curation/decide_scenario catch both uniformly as BudgetExhausted."""

PINNED_PRICE_INPUT_USD_PER_MILLION = 5.00    # gpt-5.6-sol, OpenAI published rate, verified 2026-07-16 — a CODE CONSTANT floor
PINNED_PRICE_OUTPUT_USD_PER_MILLION = 30.00  # same

class SpendBudget:
    def __init__(self, ceiling_usd: float, price_in: float, price_out: float):
        # A configured price BELOW the pinned verified rate would make the "hard"
        # ceiling meaningless (a user could set price_input_per_million_usd: 0.001
        # and reserve near-infinite headroom against a real, unchanged bill) — this
        # constructor is the single enforcement point (load_settings(), §13, ALSO
        # validates this at config-load time, before a SpendBudget is even
        # constructed; both checks exist because SpendBudget must be safe to
        # construct directly in a test without going through load_settings()).
        if price_in < PINNED_PRICE_INPUT_USD_PER_MILLION or price_out < PINNED_PRICE_OUTPUT_USD_PER_MILLION:
            raise ValueError(
                f"price_in=${price_in}/price_out=${price_out} per million tokens is below the "
                f"pinned verified floor (${PINNED_PRICE_INPUT_USD_PER_MILLION}/"
                f"${PINNED_PRICE_OUTPUT_USD_PER_MILLION}) — only raise the floor itself, via a "
                f"code-reviewed change to PINNED_PRICE_*_USD_PER_MILLION, if OpenAI's actual "
                f"published rate changes; never lower a config value below it")
        self.ceiling_usd = ceiling_usd
        self.spend_so_far_usd = 0.0
        self._price_in, self._price_out = price_in, price_out
        self._poisoned = False

    def reserve(self, payload: dict) -> float:
        """Computes this call's WORST-CASE cost from (a) reservation_basis_tokens()
        over the COMPLETE request payload (build_request_payload()'s output — never
        just its text fields, never a "typical" guess, never a hand-picked framing
        constant) and (b) payload["max_completion_tokens"] (an API-ENFORCED hard cap
        — OpenAI cannot return MORE completion tokens than requested, so this term is
        exact, not estimated). Checks spend_so_far + worst_case <= ceiling_usd BEFORE
        the caller is allowed to issue the API call — no safety margin is subtracted,
        because none is needed: reservation_basis_tokens() is a proven upper bound,
        not an estimate with unknown error. Raises BudgetExhausted if the check
        fails, OR if the budget has already been poisoned by record_actual() (see
        below) — in the poisoned state, reserve() ALWAYS raises, permanently, for the
        rest of this SpendBudget instance's lifetime. Returns the reservation amount
        (float) on success; the caller must pass it to record_actual() once the real
        response is in hand. Called before EVERY API call, including retries, which
        reserve independently, each with its own freshly-built payload.
        """
        if self._poisoned:
            raise BudgetExhausted("budget is poisoned by a prior accounting anomaly — no further calls permitted")
        worst_case = (reservation_basis_tokens(payload) * self._price_in
                      + payload["max_completion_tokens"] * self._price_out) / 1_000_000
        if self.spend_so_far_usd + worst_case > self.ceiling_usd:
            raise BudgetExhausted(f"reserving ${worst_case:.4f} would exceed the "
                                   f"${self.ceiling_usd:.2f} ceiling "
                                   f"(${self.spend_so_far_usd:.2f} already spent)")
        self.spend_so_far_usd += worst_case
        return worst_case

    def record_actual(self, reservation: float, usage: dict) -> None:
        """Called immediately after a reserved call returns. Replaces the worst-case
        reservation with the call's REAL cost (usage.prompt_tokens * price_in +
        usage.completion_tokens * price_out) — headroom the reservation over-estimated
        is returned to the budget, available for the next reserve().

        ASSERTS actual <= reservation — given reservation_basis_tokens()'s proven
        upper bound and max_completion_tokens' API-enforced cap, this can only be
        violated by a genuine accounting bug (e.g. a code path that reserved against
        the wrong text, or a future OpenAI billing change that charges for something
        not counted here). If it IS violated: this method does NOT silently
        continue. It applies the true-up honestly (the money is already spent —
        under-recording it would make the ledger wrong, not the spend smaller), sets
        self._poisoned = True, and raises BudgetPoisoned immediately. Every
        subsequent reserve() call on this instance then raises BudgetExhausted
        (above) — run_curation/decide_scenario catch that and stop the run with
        stop_reason="spend_ceiling", exactly as any other budget exhaustion. This is
        "terminate further calls on any accounting anomaly": the run halts hard the
        moment the mathematical guarantee is shown to have failed, rather than
        continuing on a ledger that is no longer provably bounded.
        """
        actual = (usage["prompt_tokens"] * self._price_in
                  + usage["completion_tokens"] * self._price_out) / 1_000_000
        self.spend_so_far_usd += actual - reservation   # true-up (always <= 0 unless poisoned below)
        if actual > reservation:
            self._poisoned = True
            raise BudgetPoisoned(f"accounting invariant violated: call cost ${actual:.4f}, "
                                  f"reserved only ${reservation:.4f} (overage ${actual - reservation:.4f}) "
                                  f"— budget poisoned, no further calls permitted")
```

Every one of Stage A, Stage B, and Judge (§4) builds its request via
`build_request_payload(model=..., system_text=..., user_text=..., max_completion_tokens=...,
reasoning_effort=cfg.reasoning_effort, schema=...)` — passing the **actual, fully-substituted
system/user prompt strings about to be sent** (never a token-count guess), the exact JSON
schema object for Stage B/Judge (`STAGE_B_RESPONSE_SCHEMA`/`JUDGE_RESPONSE_SCHEMA`, `None` for
Stage A), and **that call type's own `max_completion_tokens` cap** (3,000 / 1,500 / 1,200
respectively — see the table below) — then calls `budget.reserve(payload)` with that EXACT
dict immediately before issuing the API request (unpacking the SAME dict's fields into the
SDK call's kwargs — never a second, independently-constructed payload that could drift from
what was reserved), and `budget.record_actual(...)` immediately after. A **retry** (§15) is a
brand-new call, rebuilds its payload, and reserves independently before firing — so the
hard-ceiling guarantee holds across retries too, not just first attempts.
`test_curate.py::test_record_actual_cannot_leave_spend_above_ceiling` constructs a
tiny-ceiling budget, reserves against a real payload built via `build_request_payload`, calls
`record_actual` with a `usage` dict at the API-enforced worst case (`completion_tokens ==
max_completion_tokens`, `prompt_tokens` == `reservation_basis_tokens(payload)`'s own count,
i.e. the true guaranteed upper bound, not an approximation of it), and asserts
`spend_so_far_usd <= ceiling_usd` with no exception raised (the normal, expected case, since
`actual <= reservation` always holds here). A second case feeds `record_actual` a
deliberately anomalous `usage` (`prompt_tokens` artificially set above the reservation,
simulating a hypothetical broken invariant) and asserts `BudgetPoisoned` is raised,
`spend_so_far_usd` still reflects the true (higher) cost, and a subsequent `reserve()` call
raises `BudgetExhausted` — proving the "terminate further calls on any accounting anomaly"
contract, not merely a logged warning. A third case, `test_spend_budget_rejects_price_below_
pinned_floor`, constructs `SpendBudget(ceiling_usd=100, price_in=0.001, price_out=0.001)` and
asserts `__init__` raises `ValueError` — proving the floor guard fires independent of
`load_settings()`'s own equivalent check (§13).

**Batching & stop conditions** (`curate.py::run_curation`):

**Applicability is a precondition, not just a judge opinion.** An earlier draft sampled
`run_curation`'s `candidates` from the *entire* 8,260-candidate pool regardless of the
winning scenario — so a record with no real jurisdictional/topical connection to Scenario
A's "AI feature in the EU" framing (e.g. a US securities-enforcement record) could still be
probed under that framing, and if the judge over-broadly flagged an omission, that "evidence"
would describe a mismatch between record and scenario, not a real baseline failure. The fix:
`run_prep.py::main` filters the candidate stream by the **same deterministic `is_eligible`
predicate §7 already built and tested for the scenario-decision trial** before it ever
reaches `run_curation` — `candidates = [r for r in all_candidates if is_eligible(r,
winning_scenario)]`. This is not a new mechanism; it is applying the one that already exists
consistently to curation, not just to the trial that picked the scenario.

```python
def run_curation(client, candidates: list[dict], scenario, cfg: Settings, budget: SpendBudget) -> CurationResult:
    """
    PRECONDITION (enforced by the caller, run_prep.py::main, not re-checked here):
    every element of `candidates` already satisfies is_eligible(r, scenario) — §7.
    ordered = stratified_sample_sequence(candidates, seed=cfg.sample_seed)
    survivors: list[ProbeAndScoreResult] = []
    probed = 0
    for batch in chunk(ordered, cfg.probe_batch_size):
        for record in batch:
            try:
                result = probe_and_score_one(client, record, scenario, cfg, budget)  # Stage A + Stage B + Judge, each budget-reserved
            except BudgetExhausted:
                return CurationResult(survivors=survivors, probed=probed,
                                       spend_usd=budget.spend_so_far_usd, stop_reason="spend_ceiling")
            probed += 1
            if result["passes_failure_bar"]:
                survivors.append(result)
        log(f"{len(survivors)} survivors / {probed} probed / ${budget.spend_so_far_usd:.2f} spent")
        if len(survivors) >= cfg.target_set_size:
            return CurationResult(survivors, probed, budget.spend_so_far_usd, "target_reached")
        if probed >= cfg.probe_max_records:
            return CurationResult(survivors, probed, budget.spend_so_far_usd, "sweep_cap")
    return CurationResult(survivors, probed, budget.spend_so_far_usd, "pool_exhausted")
    """

class CurationResult(TypedDict):
    survivors: list["ProbeAndScoreResult"]
    probed: int
    spend_usd: float
    stop_reason: Literal["target_reached", "sweep_cap", "spend_ceiling", "pool_exhausted"]
```

Four possible stop reasons, checked in this priority: **(1)** a reservation fails mid-record
(`BudgetExhausted` — the hard backstop, can trigger inside a batch, unlike the other three
which are only ever checked at a batch boundary so a batch always otherwise completes
cleanly), **(2)** `target_set_size` survivors found (default 200 — goal's ceiling), **(3)**
`probe_max_records` records probed (default 400 — ~4.8% of the 8,260 pool; goal #11's floor
is never relaxed to compensate for a low hit rate, so this cap existing at all is intended
behavior, not a bug), **(4)** the candidate pool itself is exhausted (only possible if
`probe_max_records` exceeds the pool size).

**Per-call budget & documented cost estimate** (three calls per record: Stage A, Stage B,
Judge — Judge is defined in §4). The "typical input tokens" column below is a **planning
estimate only**, used solely for the illustrative $-total math that follows — the *actual*
`SpendBudget.reserve()` call for each of these never uses this table; it measures
`estimate_tokens()` of the real, fully-rendered prompt text at call time (above), which is
always >= these typical figures and is what the hard-ceiling proof actually relies on:

| Call | `max_completion_tokens` cap (= completion reservation basis) | Typical input tokens (planning only) | Typical completion tokens |
|---|---|---|---|
| Stage A | 3,000 | ~350 (system+task) | ~250–600 (a short draft; reasoning models spend some of this budget on hidden reasoning tokens before the visible draft) |
| Stage B | 1,500 | ~300 | ~150–400 (structured JSON is short) |
| Judge | 1,200 | ~900 typical (record summary + a typical-length Stage A draft) — the actual reservation instead measures the REAL draft embedded that run, so an unusually long draft costs more reserved headroom, never an under-reservation | ~150–350 |

At the pinned rate (**$5.00 / 1M input, $30.00 / 1M output** — re-verify against OpenAI's
current pricing page before running, since this can drift; `config.yaml`'s `price_*` keys
are the single override point if it does): a **typical** record (all 3 calls) costs roughly
`(1,550 in × $5 + 1,000 out × $30) / 1e6 ≈ $0.038`; the **reserved worst case** per record
(every call maxing its own cap) is `(1,550 in × $5 + 5,700 out × $30) / 1e6 ≈ $0.179`. At
`probe_max_records=400`: **typical total ≈ $15, reserved worst case ≈ $72.** The
scenario-decision trial (§7) reserves from the **same** `SpendBudget` instance: 30 records ×
2 scenarios × 3 calls, typical ≈ $2.30, reserved worst case ≈ $10.7. **Combined reserved
worst case ≈ $83**, just under the **$90** ceiling — chosen so a run can complete the full
scenario trial *and* the full curation sweep even in the worst case, while a genuine runaway
(e.g. a misconfigured `max_completion_tokens`) still hits a hard, provable wall at $90, not an
after-the-fact overshoot.

**Determinism/reproducibility.** Every probe call's raw request+response is written to
`data/scratch/probe_log/<record_artifact_id>_{stage_a,stage_b,judge}.json` (prompt, response,
`usage` including the reasoning-token breakdown, timestamp, model id, the `SpendBudget`
reservation and actual cost for that call). A run is "replayed" by re-invoking `run_curation`
with `--replay data/scratch/probe_log/` (a CLI flag on `run_prep.py`): cached responses are
read from disk instead of calling the API for any `(record_id, stage)` pair already logged —
**and replayed calls never touch `SpendBudget.reserve()`** (no new spend, since no new call is
made) — making replay free and exact for those pairs; new records (e.g. a larger
`probe_max_records` on a re-run) still call the API and still reserve normally. This is the
practical meaning of "the same probe run replays to the same result" given the model call
itself isn't literally deterministic token-for-token — the *log* is the source of truth for a
specific run's result.

---

## 4. Scoring — deterministic first

Three independent scorers, one per failure mode, each returning a small typed result;
`passes_failure_bar()` combines them.

### Why the earlier taxonomy over-claimed unfairness as evidence, and the fix

A coarse Stage B prompt like "the AI-assisted decisioning feature in the EU" does **not**
uniquely identify one Carver record — several genuinely distinct, genuinely real regulatory
developments can plausibly govern the same jurisdiction × domain-bucket combination at once.
Comparing baseline's answer against exactly one record's URL/compliance-date therefore risks
mislabeling a **correct alternative source** as a failure. Two changes fix this without
weakening what the deterministic checks are for:

1. **Sharper grounding (reduces, but cannot prove away, the ambiguity).** §3's Stage B prompt
   is extended with two more coarse, still non-answer-leaking signals already available on
   the record: `{{UPDATE_TYPE_PHRASE}}` (a natural rendering of `update_type` — "there's been
   a new enforcement action" / "new guidance" / "a proposed rule" / etc. — narrows which
   *kind* of development is meant) and `{{RECENCY_PHRASE}}` ("in the past few months" — the
   record's own recency, goal's sharpest selection axis, is already implicit in why the
   record is a candidate at all, §2's `>= 2026-03-01` filter). Neither leaks the regulator,
   citation, or date — both are coarse categorical/temporal framing, same class of fact as
   the jurisdiction/domain-bucket phrases already allowed.
2. **Scoring no longer assumes uniqueness (the actual fix — task §4's stated "or" branch:
   "constrain deterministic scoring to claims that can validly be attributed to that
   record").** Only claims that are objectively checkable **regardless of which specific
   obligation the model had in mind** count as failure evidence. A real, resolving URL that
   doesn't match ground truth is **not penalized** — it may well be a legitimate alternative
   source (exactly the checker's concern) — it is recorded as information only. A compliance
   date is only ever judged "wrong" once the citation is independently confirmed to be
   *this* record (i.e. baseline itself asserted the correct URL) — at that point there is no
   remaining ambiguity about which document the date claim is even about, so a mismatch is
   unarguable.

### `score_citation(stage_b, record) → CitationScore`

```python
class CitationScore(TypedDict):
    outcome: Literal["citation_correct", "citation_missing", "citation_alternative_real", "citation_fabricated"]
    baseline_url: str | None
    matched_ground_truth_url: str | None
    is_failure: bool   # True iff outcome == "citation_fabricated" — see below
```

Algorithm:
1. Ground truth = `extract_urls()` applied to `reg_rules + reg_statutes + reg_other_ref`
   (the same extraction used in §2), normalized (strip trailing `/`, lowercase scheme+host,
   keep path/query as-is — real regulator query strings like `?uri=CELEX%3A...` are
   significant and not touched).
2. If `stage_b.source_url` is `null` → `citation_missing`, `is_failure = False`. **An honest
   "I don't know" explicitly invited by the Stage B system prompt ("if you are not confident
   ... say so — do not guess") is not one of goal #2's three named failure modes (fabricated
   citation / wrong compliance date / missed obligation) — it is safe, correctly-calibrated
   uncertainty, and treating it as failure evidence would reward the model for confidently
   guessing over honestly abstaining, backwards from what a compliance guardrail should
   reward.** Still logged (never silently dropped) so the human reviewer can see the model
   was asked and declined.
3. Else if `stage_b.source_url` normalized exactly matches a ground-truth URL →
   `citation_correct`, `is_failure = False`.
4. Else (`source_url` present, no exact match): call `resolve_url(stage_b.source_url, cache)`.
   - Resolves → `citation_alternative_real`, `is_failure = False`. **This is the fair-test
     fix**: a real, live URL that isn't OUR record's ground truth is not automatically wrong
     — it may correctly cite a genuinely different, equally real obligation the coarse
     prompt could also have been read as asking about. Logged as an explicit flag for human
     review (§6): "baseline cited a different real source — confirm this record's OTHER
     evidence (if any) is not itself an artifact of an ambiguous question before treating it
     as strong."
   - Does not resolve → `citation_fabricated`, `is_failure = True`. **The only citation-based
     deterministic failure mode.** This is unarguable regardless of which specific obligation
     was "the" intended answer: a URL that does not resolve is objectively a dead, invented
     link no matter what the correct answer would have been — goal #4's sharpest, most
     demonstrable failure (success criterion #3: "ideally with a fabricated citation").

### `score_compliance_date(stage_b, record) → DateScore`

```python
class DateScore(TypedDict):
    outcome: Literal["date_correct", "date_wrong", "date_missing", "date_uncertain_attribution", "not_applicable"]
    ground_truth_date: str | None
    baseline_date: str | None
    is_failure: bool   # True iff outcome == "date_wrong" — see below
```

- Ground truth = `record["compliance_date"]`. If empty/`null`/unparseable as ISO date →
  `not_applicable`, `is_failure = False` — the record is not excluded from candidacy; this
  dimension simply contributes no evidence for it (many `bulletin`/`advisory` records
  legitimately carry no compliance date, as confirmed in the live sample record).
- Else if `stage_b.compliance_date == null` → `date_missing`, `is_failure = False` — same
  honest-abstention reasoning as `citation_missing` above; not one of the three named
  failure modes.
- Else if `citation.outcome != "citation_correct"` (computed by `score_citation`, passed in as
  a parameter — see the updated signature below) → `date_uncertain_attribution`,
  `is_failure = False`. **The other half of the fair-test fix**: if baseline did not
  independently confirm it was talking about *this* record's source (citation missing,
  fabricated, or a different real one), a date claim's correctness can't be attributed to
  this record either — the date might be perfectly correct for whatever *other* document
  baseline actually had in mind. Logged, not counted.
- Else (`citation.outcome == "citation_correct"` — baseline unambiguously identified THIS
  record's source): tolerance is **exact match, 0-day** (a compliance *deadline* is a
  specific date; "close" is still wrong for an audit-trail claim). Matching ground truth →
  `date_correct`. Not matching → `date_wrong`, `is_failure = True` — now unarguable: baseline
  has already proven, via its own correct citation, that it is talking about this exact
  document, so a wrong date about that same document is a real, unambiguous error.

```python
def score_compliance_date(stage_b: StageBResult, record: dict, citation: CitationScore) -> DateScore: ...
```

(`score_citation` is always called first; its result is threaded into `score_compliance_date`
— see `probe_and_score_one`'s updated call order below.)

### The shared Judge/Verdict contract (used by prep's curation AND the template's runtime guardrail — task §4 + rubric §1)

**One prompt family, one response schema, one post-processing algorithm** — used by
`prep/mastra_prep/judge.py::run_judge` (always called with exactly one obligation) **and**
`template/src/processors/carverGuardrail.ts`'s verdict stage (§9b, called with 1–5
obligations). This is what makes "the same scorers that curate the set ship as the eval
harness" (goal #4) literally true at the call-site level, not just true in spirit: both
halves ask the model the identical question, in the identical shape, differing only in how
many obligations are batched into one call.

**`prep/prompts/judge_system.md`** (verbatim; no scenario-specific substitution — the judge
is scenario-agnostic, it only ever sees obligations and a draft):

```markdown
You are a compliance obligation checker. You are given one or more regulatory obligations
(each with an id, title, key requirements, and objective) and a single piece of drafted text
— a work product an assistant produced. For EACH obligation, answer three separate questions,
in this order — do not skip to "violation" without first confirming the first two:

1. **applies_to_draft**: Does this specific obligation genuinely govern the specific activity
   or content the draft is about — not merely a loosely related topic? A record about, say,
   biometric data collection does NOT apply to a draft about a text-only credit-scoring
   feature just because both are "AI". If the obligation's actual subject matter does not
   match what the draft is actually doing, applies_to_draft is false, and you MUST NOT mark
   "violation" — the correct verdict is "compliant" (nothing here for this obligation to
   flag) regardless of anything else.
2. **omission_material**: ONLY relevant if applies_to_draft is true. Would a real compliance
   reviewer expect THIS document — given its actual type and length (a short release note, an
   email, is not a full technical filing) — to contain the missing content? Flagging a
   two-paragraph announcement for lacking a full technical documentation dossier is not a
   material omission; flagging it for failing to disclose a legally-required consumer notice
   that a document of exactly this type and audience should carry IS material. If the missing
   content would not realistically belong in a document of this type, omission_material is
   false, and the verdict must be "compliant", not "violation".
3. **verdict**: "violation" is permitted ONLY when applies_to_draft AND omission_material are
   both true, AND the draft actually contradicts or omits a specific listed key requirement.
   Otherwise "compliant". Use "uncertain" (with applies_to_draft/omission_material set to your
   best honest read) whenever you are not confident, rather than guessing "compliant" or
   "violation".

Judge only from what is stated in the obligations and the draft below — do not use outside
regulatory knowledge to invent additional requirements that are not listed.
```

**`prep/prompts/judge_user.md`**:

```markdown
## Obligations
{{OBLIGATIONS_JSON}}

## Draft
{{DRAFT_TEXT}}

Return exactly one verdict per obligation id listed above.
```

| Token | Substituted with |
|---|---|
| `{{OBLIGATIONS_JSON}}` | `json.dumps([{"id": o.id, "title": o.title, "key_requirements": o.key_requirements, "objective": o.objective} for o in obligations], ensure_ascii=False, indent=2)` |
| `{{DRAFT_TEXT}}` | the Stage A `draft_text` (prep) or the drafted output being enforced (template) |

**Response schema** (OpenAI Structured Outputs, prep; the identical shape re-expressed as a
Zod schema for the template's `agent.generate(prompt, { output: ... })` call — see §9b):

```python
JUDGE_RESPONSE_SCHEMA = {
    "name": "obligation_judge",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "obligation_id": {"type": "string"},
                        "applies_to_draft": {"type": "boolean"},
                        "omission_material": {"type": "boolean"},
                        "verdict": {"type": "string", "enum": ["compliant", "violation", "uncertain"]},
                        "confidence": {"type": "number"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["obligation_id", "applies_to_draft", "omission_material",
                                 "verdict", "confidence", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["verdicts"],
        "additionalProperties": False,
    },
}

class JudgeObligationInput(TypedDict):
    id: str
    title: str
    key_requirements: list[str]
    objective: str

class JudgeVerdict(TypedDict):
    obligation_id: str
    applies_to_draft: bool     # §4's applicability fix — see score_missed_obligation below
    omission_material: bool    # §4's materiality fix
    verdict: Literal["compliant", "violation", "uncertain"]
    confidence: float
    rationale: str

class JudgeResult(TypedDict):
    verdicts: list[JudgeVerdict]

def run_judge(client, obligations: list[JudgeObligationInput], draft_text: str, cfg: Settings, budget: "SpendBudget") -> JudgeResult:
    """Always takes a LIST (prep passes exactly one element; the template's verdict
    stage passes 1-5). budget.reserve() is called before the request using this call
    type's max_completion_tokens cap (1,200 for a single-obligation prep call; the
    template's verdict stage is not budget-gated the same way since it's a live
    runtime call, not a curation cost — see §9b). Post-processing per
    parse_and_validate_verdicts() below."""
```

**Validation of returned obligation IDs (rubric #1 — exact, so §9c can never dereference
`undefined`):**

```python
def parse_and_validate_verdicts(raw_response: str, requested_ids: list[str]) -> JudgeResult:
    """
    1. Parse JSON. On failure: caller retries the call ONCE with the same input; if the
       retry also fails to parse, every requested_id gets the omission fallback (step 3).
    2. Build an index from obligation_id -> verdict entry using FIRST occurrence only;
       if the response lists the same obligation_id twice, the second and later entries
       are dropped (a stray duplicate never gets to "vote twice").
    3. For every id in requested_ids NOT present in the index (the model omitted it):
       synthesize verdict="uncertain", confidence=0.0, applies_to_draft=False,
       omission_material=False, rationale="model omitted this obligation from its
       response". An omission is NEVER silently treated as "compliant" (would hide a
       real risk) or "violation" (would fabricate evidence) — "uncertain" is the only
       safe default, and it excludes the obligation from failure/violation accounting
       exactly like a genuine low-confidence verdict would (§4's `is_failure` rule /
       §9c's enforcement both already treat "uncertain" as a non-event).
       applies_to_draft/omission_material default to False (never True) so an
       omitted verdict can never accidentally satisfy §4's is_failure conjunction
       even if some future refactor forgets to also check `verdict`.
    4. Entries in the response whose obligation_id is NOT one of requested_ids
       (hallucinated or stale id) are dropped silently — never looked up against
       data/cleared/ or the narrowed candidate list, which is exactly what prevents
       §9c from ever dereferencing an id that doesn't exist in its own candidate set.
    5. Return exactly one JudgeVerdict per id in requested_ids, in requested_ids order.
    """
```

This single algorithm is implemented once in prep (`judge.py::parse_and_validate_verdicts`)
and once in the template (`evals/scorers.ts::parseAndValidateVerdicts`, also called by
`carverGuardrail.ts`'s verdict stage) — same five steps, same fallback semantics, tested
against the shared `scoring_golden.json` fixture family (§12) on both sides.

### `score_missed_obligation(record, scenario, judge_result, obligation_id) → ObligationScore`

```python
class ObligationScore(TypedDict):
    outcome: Literal["violation", "compliant", "uncertain", "not_applicable"]
    confidence: float
    applies_to_draft: bool
    omission_material: bool
    is_failure: bool

def score_missed_obligation(record: dict, scenario: "ScenarioSpec", judge_result: JudgeResult,
                             obligation_id: str) -> ObligationScore:
    """
    If not is_eligible(record, scenario) (§7's own deterministic predicate, reused
    here defensively): outcome="not_applicable", is_failure=False, and the judge's
    verdict for this dimension is not even consulted. In normal operation this
    branch is never reached — `run_curation`'s caller-side filter (above) already
    guarantees every record it probes satisfies is_eligible — but keeping the check
    here too means score_missed_obligation is safe to call directly (e.g. from a
    test, or from a future caller that doesn't go through run_curation) without
    silently trusting an unenforced precondition.

    Otherwise, looks up obligation_id in judge_result.verdicts (guaranteed present
    — see parse_and_validate_verdicts step 5, every requested id always has an
    entry). is_failure = (verdict == "violation" AND confidence >=
    cfg.judge_confidence_floor AND applies_to_draft AND omission_material) — ALL
    FOUR conditions required, not just the first two. A judge that says "violation"
    but also says applies_to_draft=False or omission_material=False is
    self-contradictory (the system prompt instructs it never to do this) and is
    treated as NOT a failure regardless — the deterministic conjunction, not the
    model's own verdict label, is authoritative over is_failure.
    """
```

`"uncertain"`/`"not_applicable"` outcomes, `"violation"` verdicts below `judge_confidence_
floor` (`>= 0.7`, §13), and `"violation"` verdicts where the judge itself did not also
confirm both `applies_to_draft` and `omission_material` are **never** treated as failures —
this is the near-miss guard for the fuzziest
of the three checks (rubric #14). The judge is called **once** per record during curation
(cost control, §3); malformed-JSON handling is covered by `parse_and_validate_verdicts`
above, which never defaults a parse failure to `"violation"`.

### The failure bar (task §4, rubric #14 — exact)

```python
def passes_failure_bar(citation: CitationScore, date: DateScore, obligation: ObligationScore) -> tuple[bool, list[str]]:
    """A record is admitted iff AT LEAST ONE of the three is_failure flags is True.
    Given the taxonomy above, is_failure is True ONLY for outcome ==
    "citation_fabricated" (citation), "date_wrong" (date), or "violation" above the
    confidence floor (obligation) — i.e. evidence_modes can only ever contain values
    from goal #2's three named failure modes {fabricated citation, wrong compliance
    date, missed obligation}, never an honest-abstention or plausible-alternative
    outcome. Returns (admitted, evidence_modes) where evidence_modes lists every
    failing dimension's `outcome` string (a record can carry multiple pieces of
    evidence). A record where all three are non-failures (citation_correct/missing/
    alternative_real, date_correct/missing/uncertain_attribution/not_applicable,
    obligation compliant/uncertain) is REJECTED — this is the near-miss exclusion: no
    partial credit, no scoring threshold to tune.
    """
    evidence = []
    if citation["is_failure"]: evidence.append(citation["outcome"])
    if date["is_failure"]: evidence.append(date["outcome"])
    if obligation["is_failure"]: evidence.append(obligation["outcome"])
    return (len(evidence) > 0, evidence)
```

No weighting, no "2 of 3," no fuzzy score threshold — a single real, recorded failure mode is
sufficient and necessary. This keeps the bar auditable in the human-review step (§6): a
reviewer looks at 1–3 concrete `evidence_modes` strings, each one of exactly the three
canonical failure modes, backed by the actual baseline response text, never a black-box
composite score and never a mislabeled "safe uncertainty" or "plausible alternative."

### Tying it together: `probe_and_score_one`

```python
class ProbeAndScoreResult(TypedDict):
    record_id: str
    disqualified_reason: Literal["no_resolving_ground_truth_url"] | None   # set only by the URL gate, §2
    resolving_urls: list[tuple[str, str]]                                   # (name, url) pairs that resolved at probe time — §5's citation-selection input
    stage_a: StageAResult | None            # None iff disqualified_reason is set (never reached)
    stage_b: StageBResult | None            # None iff disqualified_reason is set
    judge: JudgeResult | None               # None iff disqualified_reason is set
    citation: "CitationScore | None"
    date: "DateScore | None"
    obligation: "ObligationScore | None"
    passes_failure_bar: bool                # always False when disqualified_reason is set
    evidence_modes: list[str]               # always [] when disqualified_reason is set

def probe_and_score_one(client, record: dict, scenario: "ScenarioSpec", cfg: Settings,
                         budget: "SpendBudget") -> ProbeAndScoreResult:
    """
    0. URL GATE (§2, first, before any LLM call): extract_urls() over the record's
       reg-reference prose, resolve_url() each candidate. If NONE resolve, return
       immediately with disqualified_reason="no_resolving_ground_truth_url",
       passes_failure_bar=False, evidence_modes=[] — zero budget.reserve() calls are
       made; this record never reaches Stage A/B/Judge at all. If >=1 resolves,
       proceed with resolving_urls populated and disqualified_reason=None.
    1-3. Otherwise, runs Stage A, Stage B, and the Judge in order, each gated by
       budget.reserve(...) immediately before its own API call and
       budget.record_actual(...) immediately after (§3):
      1. Stage A (draft_text)
      2. Stage B (citation/date structured probe)
      3. Judge, called with the record itself as the single obligation and Stage A's
         draft_text as the draft (run_judge(client, [as_judge_obligation(record)],
         stage_a.draft_text, cfg, budget))
    Then scores in this order (citation MUST be computed first — score_compliance_date
    takes the resulting CitationScore as a parameter, §4):
      citation = score_citation(stage_b, record)
      date = score_compliance_date(stage_b, record, citation)
      obligation = score_missed_obligation(record, scenario, judge, record["id"])
      passes_failure_bar(citation, date, obligation)
    Always returns a full result (even when passes_failure_bar is False, for either
    reason) — curation logs every probed record to data/scratch/probe_log/ regardless
    of outcome (§3), so near-misses (and URL-gate disqualifications) are inspectable
    for debugging and reporting, just never written to data/cleared/.
    Raises BudgetExhausted if any of the three reserve() calls fails — the caller
    (run_curation / decide_scenario) catches this to stop the run, per §3.
    """
```

`as_judge_obligation(record) -> JudgeObligationInput` is a one-line adapter
(`{"id": record["artifact_id"], "title": record["title"], "key_requirements":
record["key_requirements"], "objective": record["objective"]}`) — the same shape §9b's
guardrail verdict stage builds from `data/cleared/` records at runtime, keeping the "what the
judge is shown" contract identical in both places.

---

## 5. The cleared-record schema — the seam between the halves

Pinned exactly, once, here — this **is** the literal JSON shape written by
`prep/mastra_prep/schema.py::to_json()` and read by `template/src/schema.ts`'s Zod schema.
There is no separate "illustrative" version: the JSON keys below are `snake_case` and both
halves' schema definitions use those exact key names verbatim (the TS Zod schema is **not**
camelCased — one fewer moving part, and the vendored file is meant to be human-readable as
shipped). **Not shared as code** (goal decision #1 forbids `template/` depending on
`prep/`) — each half hand-maintains its own schema object conforming to this table, locked by
the contract tests in §12/§14 (`test_schema.py` on the Python side, `schema.test.ts`
Zod-parsing the vendored JSON on the TS side, plus the duplicated `scoring_golden.json`
fixture, §12).

### Scorer-outcome → `BaselineFailure.mode` mapping (rubric §7 — exact, no ambiguity)

Given §4's revised taxonomy (issue: the earlier draft's `citation_missing`/`citation_wrong_
real`/`date_missing` outcomes could be `is_failure=True`, which risked labeling honest
uncertainty or a plausibly-correct alternative citation as a "failure" — fixed by making
`is_failure` True for exactly one outcome per dimension), this mapping is now a **closed,
3-entry identity map onto goal #2's own three named failure modes** — there is no fourth
category left to name or reconcile:

```python
SCORE_OUTCOME_TO_FAILURE_MODE: dict[str, str] = {
    # Only outcomes where is_failure=True ever reach this map (only such dimensions
    # become BaselineFailure entries at all, §4's passes_failure_bar) — so this map
    # is exhaustive over "citation_fabricated", "date_wrong", "violation" and NOTHING
    # else; "citation_missing"/"citation_alternative_real"/"date_missing"/
    # "date_uncertain_attribution"/"not_applicable"/"compliant"/"uncertain" can never
    # appear here because is_failure is never True for them.
    "citation_fabricated": "citation_fabricated",   # goal #2's "fabricated citation"
    "date_wrong": "date_wrong",                     # goal #2's "wrong compliance date"
    # ObligationScore.outcome -> mode (RENAMED: the scorer's internal literal is
    # "violation" — a generic name reused by the runtime guardrail's verdict stage,
    # §9b, which asks the identical judge question about a live draft, not a
    # curation-time obligation record — but the shipped dataset's evidence label is
    # the more descriptive "missed_obligation")
    "violation": "missed_obligation",               # goal #2's "missed obligation"
}
```

`BaselineFailure.stage` is **derived, never set independently** — a pure function of `mode`,
so it can never disagree with the mode that produced it:

```python
STAGE_OF_MODE: dict[str, str] = {
    "citation_fabricated": "B",
    "date_wrong": "B",
    "missed_obligation": "A",
}
# citation_fabricated/date_wrong are produced exclusively by Stage B's structured
# probe; missed_obligation is produced exclusively by Stage A's draft + the Judge
# (which scores Stage A's output, §4) — these sets are disjoint by construction
# (§4's scorers never write a mode outside their own dimension), so STAGE_OF_MODE
# has no ambiguous entries and to_json() never needs a fallback branch.
```

`baseline_response_excerpt` for a `citation_*`/`date_*` mode is Stage B's response rendered
as `f"source_name={r.source_name!r} source_url={r.source_url!r} compliance_date={r.compliance_date!r}"`
(truncated to 1000 chars); for `missed_obligation` it is Stage A's `draft_text` (truncated to
1000 chars). `judge_rationale` is populated from `judge_result.verdicts[i].rationale`
**only** when `mode == "missed_obligation"`; it is `null` for every `citation_*`/`date_*`
mode (there is no judge involved in producing those).

### Citation derivation — which of possibly several ground-truth URLs ships

§2's URL gate requires only that **at least one** ground-truth URL (extracted from
`reg_rules`/`reg_statutes`/`reg_other_ref`) resolves *at probe time*; a record can have several
(the sample record inspected during spec research had five reg-reference strings across three
arrays). `probe_and_score_one`'s URL gate (§2, §4) already computes and stores every resolving
`(name, url)` pair as `ProbeAndScoreResult.resolving_urls` — human review does **not**
re-resolve anything; it reads that already-computed list. Picking "the" citation is a
**human-review-time decision** (§6), not automatic: if `resolving_urls` has exactly one
element, it is auto-selected with no prompt (there is no real choice to make); if it has more
than one, the reviewer is shown all of them (`name` = the containing string's text before the
parenthetical URL, trimmed, already computed at gate time) and **must** pick exactly one
before `record_signoff` can proceed — `citation.name`/`citation.url` are that pick, verbatim,
never edited or reworded.

### `ClearedRecord` — exact JSON shape (Python `TypedDict`, `snake_case` keys as-shipped)

```python
class BaselineFailure(TypedDict):
    mode: Literal["citation_fabricated", "date_wrong", "missed_obligation"]   # exactly goal #2's three named modes — no fourth category
    stage: Literal["A", "B"]                  # = STAGE_OF_MODE[mode], always
    baseline_response_excerpt: str            # verbatim (<=1000 chars), never paraphrased
    judge_rationale: str | None               # non-null iff mode == "missed_obligation"

class ClearedRecord(TypedDict):
    id: str                                    # = source artifact_id, non-empty
    title: str                                 # verbatim from extract_record(); never edited (§6)
    regulator_name: str
    jurisdiction: dict                         # {"scope": str, "country": str|None, "bloc": str|None, "region_name": str|None}
                                                # — a subset of the raw field; `locality`/`reasoning` dropped (goal constraint + unneeded specificity)
    update_type: str
    impact_label: Literal["high"]              # by construction (goal #3); typed narrowly on purpose
    objective: str                             # verbatim
    what_changed: str                          # verbatim
    why_it_matters: str                        # verbatim
    key_requirements: list[str]                # verbatim, non-empty (candidate filter guarantee)
    compliance_date: str | None                # ISO 8601 date or null (many legitimately have none)
    citation: dict                             # {"name": str, "url": str} — the ONE reviewer-selected citation (above)
    impacted_business: dict                    # {"size": list[str], "type": list[str], "industry": list[str]} — subset (raw field's `other_notes`/`jurisdiction` dropped as redundant with the top-level `jurisdiction`/`why_it_matters`)
    impacted_functions: list[str]
    scenario: Literal["A", "B"]                 # which scenario this record was probed/cleared under
    baseline_failures: list[BaselineFailure]    # >= 1 element, enforced by validate_cleared_record()
    human_review: dict                          # HumanReview (§6): {"reviewer": str, "reviewed_at": str (ISO datetime), "attestation": Literal["approved"], "obligation_applies_confirmed": bool|None, "artifact_capable_of_violation_confirmed": bool|None, "omission_materiality_confirmed": bool|None} — see §6; "rejected" never reaches this file at all
    source: dict                                # {"artifact_id": str, "topic_id": str, "source_id": str, "snapshot_date": Literal["2026-07-11"]}
    probed_at: str                              # ISO datetime of the probe_and_score_one() call that produced baseline_failures
    model_id: Literal["openai/gpt-5.6-sol"]
    model_cutoff: Literal["2026-02-16"]
```

Explicitly **absent**: `relevance` (any form), `category`/`class_system`/`class_sector`/
`class_leaf` (topic-catalog taxonomy), `locality`/`jurisdiction.reasoning`, `human_review.
notes` (dropped — there is no free-text reviewer note field once `edit-then-approve` is
removed, §6; a rejection's reason lives only in `data/scratch/review_rejections.jsonl`,
never in a shipped record), any field not listed above. `validate_cleared_record()` rejects
(returns `(False, [...])`) any object containing an unlisted top-level key, an empty
`baseline_failures`, a `human_review.attestation` other than exactly `"approved"`, or a
`BaselineFailure` whose `stage` disagrees with `STAGE_OF_MODE[mode]` — this is the
schema-level half of the "impossible to ship unreviewed" gate (§6 has the other half).

### TypeScript mirror (`template/src/schema.ts`) — identical keys, `snake_case`

```typescript
export const BaselineFailureSchema = z.object({
  mode: z.enum(["citation_fabricated", "date_wrong", "missed_obligation"]),
  stage: z.enum(["A", "B"]),
  baseline_response_excerpt: z.string(),
  judge_rationale: z.string().nullable(),
});

export const ClearedRecordSchema = z.object({
  id: z.string(),
  title: z.string(),
  regulator_name: z.string(),
  jurisdiction: z.object({ scope: z.string(), country: z.string().nullable(),
    bloc: z.string().nullable(), region_name: z.string().nullable() }),
  update_type: z.string(),
  impact_label: z.literal("high"),
  objective: z.string(),
  what_changed: z.string(),
  why_it_matters: z.string(),
  key_requirements: z.array(z.string()).min(1),
  compliance_date: z.string().nullable(),
  citation: z.object({ name: z.string(), url: z.string().url() }),
  impacted_business: z.object({ size: z.array(z.string()), type: z.array(z.string()),
    industry: z.array(z.string()) }),
  impacted_functions: z.array(z.string()),
  scenario: z.enum(["A", "B"]),
  baseline_failures: z.array(BaselineFailureSchema).min(1),
  human_review: z.object({ reviewer: z.string(), reviewed_at: z.string(),
    attestation: z.literal("approved"),
    obligation_applies_confirmed: z.boolean().nullable(),
    artifact_capable_of_violation_confirmed: z.boolean().nullable(),
    omission_materiality_confirmed: z.boolean().nullable() }),
  source: z.object({ artifact_id: z.string(), topic_id: z.string(), source_id: z.string(),
    snapshot_date: z.literal("2026-07-11") }),
  probed_at: z.string(),
  model_id: z.literal("openai/gpt-5.6-sol"),
  model_cutoff: z.literal("2026-02-16"),
}).strict();   // .strict() rejects any unlisted key, mirroring validate_cleared_record()'s
                // Python-side rejection of unlisted top-level keys
export type ClearedRecord = z.infer<typeof ClearedRecordSchema>;
```

`schema.test.ts` parses the real `src/data/cleared-set.json` at test time with this exact
schema; a shape drift between the two halves fails CI immediately rather than at runtime.

---

## 6. Human review — the clearance gate

**What the reviewer sees** (`review.py::present_for_review`): a formatted terminal/markdown
block per candidate record showing: title, regulator, jurisdiction, the `baseline_failures`
evidence (mode + verbatim baseline excerpt, side by side with the ground-truth citation/date/
key_requirements it's being checked against), and — if more than one ground-truth URL
resolved (§5) — every resolving URL as numbered options for the citation-selection prompt.
**When `missed_obligation` is among the record's evidence modes**, additionally: the scenario
eligibility result that gated this record into curation at all (§4's "applicability is a
precondition" fix — shown as confirmation context, not re-asked), and the judge's own
`applies_to_draft`, `omission_material`, and `rationale` for that specific verdict. No raw
file paths, no `output_data` internals — only what would ship.

**What they attest to** (`record_signoff`) — a forced-choice CLI prompt with **exactly two**
terminal outcomes, deliberately narrowed from an earlier draft that allowed editing `title`/
`why_it_matters`: that capability is **removed** because editing extracted annotation text is
paraphrasing a record, one of goal #11's explicitly forbidden ways to reach the set — there is
no line between "a redaction/clarity edit" and "paraphrasing" that a schema can enforce, so
the only safe contract is no edits at all.

**When `missed_obligation` is among the evidence modes**, three additional yes/no questions
are asked **before** the approve/reject choice is even offered (rubric #2's fix — "provably
fails" must rest on more than the judge's own say-so):

1. *"Does this obligation genuinely apply to [the fictional firm]'s described activity, not
   merely a loosely related topic?"*
2. *"Is the drafted artifact/action capable of violating this obligation — i.e. is this the
   kind of document where the requirement would actually need to appear?"*
3. *"Is the omission the judge flagged materially real in this context, not a technicality?"*

**Any "no" forces rejection outright** — the CLI does not offer `approve` at all in that case,
and does not offer a way to "keep the record but drop the missed_obligation evidence" (that
would be an edit to `baseline_failures`, forbidden by the same no-edits rule as `title`). A
record either stands on its curated evidence as a whole, or it doesn't ship.

1. **`approve`** — ships the record's `ClearedRecord` fields **exactly as `extract_record()`
   produced them**, plus the reviewer's citation pick (if a pick was needed, above) and the
   sign-off metadata, including the three sub-attestations above (`True`) when applicable.
   `record_signoff(record, reviewer, obligation_confirmations)` is a pure "attach
   `human_review` and `citation`" operation; it has no parameter through which any extracted
   field's value could be supplied or overridden — there is no code path capable of writing
   edited prose, by construction, not merely by convention.
2. **`reject`** — logged to `data/scratch/review_rejections.jsonl` (`{record_id, reviewer,
   reason, rejected_at}`, `reason` including which of the three questions, if any, triggered
   an automatic rejection) and dropped. `attestation` is written as the literal `"approved"`
   only on the `approve` path (§5); a `"reject"` never produces a `ClearedRecord` at all —
   there is no such thing as a rejected record living in `data/cleared/` with a rejected flag,
   and no `notes` field exists on a shipped record for a reviewer to leave commentary that
   might drift from the verbatim source over time.

### `human_review` — a structured attestation, not a single flag

```python
class HumanReview(TypedDict):
    reviewer: str
    reviewed_at: str
    attestation: Literal["approved"]
    obligation_applies_confirmed: bool | None          # question 1 above; None iff missed_obligation not in evidence_modes
    artifact_capable_of_violation_confirmed: bool | None   # question 2
    omission_materiality_confirmed: bool | None        # question 3
```

`validate_cleared_record()` (§5) enforces the conjunction: if `"missed_obligation"` is in
`baseline_failures`' modes, all three confirmation fields must be exactly `True` (never
`False`, never `None`) — raises otherwise. If `missed_obligation` is **not** among the
evidence modes, all three must be `None` (there is nothing to confirm, and a stray `True`
here would misrepresent that a check happened when it didn't).

**Impossible to ship unreviewed, or reviewed without addressing applicability, by
construction:**
1. `ClearedRecord.human_review.attestation` is a **required** field typed `Literal["approved"]`
   — Python `TypedDict` has no runtime enforcement, so `validate_cleared_record()` (called by
   both `to_json()` before every write and by a pre-commit-friendly `prep/run_prep.py
   --verify-cleared` command) explicitly checks the value is exactly `"approved"`, **and** the
   three-confirmation conjunction above, and **fails the write** (raises, non-zero exit) if
   either is not satisfied.
2. `run_curation`'s survivors (§3) are written only to `data/scratch/candidates_for_review.
   jsonl` — **never directly to `data/cleared/`**. The only code path that writes to
   `data/cleared/cleared_records.json` is `review.py`'s CLI after an `approve` attestation.
   There is no batch/auto-approve flag anywhere in `config.yaml` or the CLI — reaching
   `data/cleared/` requires a human in the loop for every single record, with no code path
   around it, and no way to skip the three questions when `missed_obligation` evidence is
   present.
3. `test_schema.py::test_no_unreviewed_records_in_cleared_dir` re-parses whatever is
   currently in `data/cleared/cleared_records.json` (if present) and asserts every entry's
   `human_review.attestation == "approved"` AND the three-confirmation conjunction — a
   regression test against someone hand-editing the file later.

### Anti-padding contract (goal #11 — every forbidden shortcut, named and mechanically blocked)

| Forbidden shortcut (goal #11) | Mechanical block |
|---|---|
| Loosening the date cutoff | `load_settings()` raises `ValueError` if `candidate_cutoff_date < "2026-03-01"` (§13) — not just documented, enforced at config-load time |
| Admitting `medium`/`low` impact | `impact_label == "high"` is a hardcoded literal comparison in `is_candidate()` (§2) — not a config key, no override path exists anywhere |
| Admitting noisy `update_type`s | `ACTIONABLE_UPDATE_TYPES` (§2) is a Python code constant (a `frozenset` literal), not read from `config.yaml` — widening it requires an actual code change and code review, never a runtime flag |
| Accepting unresolvable citations | §2's URL gate — the first step of `probe_and_score_one`, strictly before any LLM call — requires ≥1 ground-truth reg-reference URL to **actually resolve over HTTP**; a record with none disqualifies immediately (`disqualified_reason="no_resolving_ground_truth_url"`) and is never probed at all, checked unconditionally with no config bypass |
| Waiving human review | §6 above: the only write path to `data/cleared/` is `review.py`'s `approve` action; no batch/auto-approve flag exists in code or config |
| Weakening the failure bar | `passes_failure_bar`'s OR-logic (§4) is a code constant with no override; `judge_confidence_floor` is `load_settings()`-validated `>= 0.7` (§13, raises `ValueError` below that — it cannot be silently lowered to admit near-misses); `target_set_size` is validated `<= 200` (§13) — it can shrink, never grow past the goal's ceiling |
| Under-pricing the spend ceiling to fake unlimited budget | `price_input_per_million_usd`/`price_output_per_million_usd` are `load_settings()`-validated `>=` the pinned verified rate (`PINNED_PRICE_*_USD_PER_MILLION`, §3/§13); `SpendBudget.__init__` enforces the same floor independently, so the check holds even for direct construction in a test or script that bypasses `load_settings()` |
| Loosening the date-rot upper bound | `SNAPSHOT_DATE` is a `candidates.py` code constant, not a config key at all (§13) — there is no config path to set it later than the real corpus snapshot |
| Synthesizing/paraphrasing records | §6's `approve`-only, no-edit review policy above: every field in a shipped `ClearedRecord` traces to `extract_record()`'s direct output (or, for `baseline_failures`/`human_review`/`citation`, to a probe/review action that never rewrites source prose) — there is no LLM-rewrite step anywhere in the `data/cleared/` write path |

---

## 7. Scenario decision procedure

**Sequencing clarification.** Goal #10 says the scenario is "decided by the probe, once, at
the end of the prep stage." Read literally this could suggest deciding *after* full curation
— but Stage A's task-instance prompt is itself scenario-specific (§3), so curation cannot run
before a scenario is chosen. This spec resolves the sequencing as: the decision runs as
**prep's first phase** (a small, symmetric trial), and is *locked* — treated as final and
non-relitigated — for the remainder of prep and all of the template stage. "At the end of the
prep stage" is read as "prep owns this decision and it is settled by the time prep is done,"
not "settled only once curation has already finished." This is a sequencing interpretation of
an underspecified (not contradictory) point in the goal, not a goal issue.

**Why one shared 30-record trial doesn't work.** An obligation about, say, EU financial-
promotion rules is categorically unanswerable by Scenario A's coding/product-agent framing —
probing it under Scenario A doesn't measure "does Scenario A find weaker failures here," it
measures "the question was out of domain," which is not evidence about either scenario.
Each scenario must be tried **only against records it could plausibly govern.**

```python
class ScenarioDecision(TypedDict):
    winner: Literal["A", "B"]
    strength_scores: dict[str, float]      # {"A": ..., "B": ...}
    survivor_counts: dict[str, int]        # {"A": ..., "B": ...}
    trial_size: dict[str, int]             # actual records probed per scenario (may be < scenario_trial_size)
    decided_at: str                        # ISO 8601 datetime
    evidence_path: str                     # "data/scratch/scenario_decision.json"
```

**Eligibility predicates — complete, closed, defined here (not deferred, rubric §21).** Each
scenario's eligibility is a **keyword predicate AND a jurisdiction predicate**, both fixed
code constants. Neither predicate is shown to the model (eligibility only selects which
records enter a trial and which `DOMAIN_BUCKETS` bucket phrase gets used — it never itself
becomes prompt text), so it may use any field on the record, not just the fair-test-legal
subset §3 restricts *prompts* to.

```python
SCENARIO_A_KEYWORDS: frozenset[str] = frozenset({
    "artificial intelligence", "ai", "algorithm", "algorithmic",
    "automated decision-making", "automated profiling", "profiling", "biometric",
    "biometric data", "facial recognition", "emotion recognition", "data protection",
    "data privacy", "gdpr", "personal data", "content moderation",
    "recommender system", "machine learning", "generative ai", "foundation model",
    "ai act", "algorithmic decision-making",
})

# Scenario B is split into TWO keyword sets, deliberately — a single flat OR-set
# (an earlier draft's design) let a record match on "marketing" or "advertising"
# ALONE, admitting plenty of non-financial marketing-regulation records (food
# advertising, tobacco marketing, etc.) that have nothing to do with "financial
# promotion rules". Eligibility now requires BOTH a financial-domain signal AND a
# promotional-framing signal (or a single term that already names both together).
SCENARIO_B_FINANCIAL_TERMS: frozenset[str] = frozenset({
    "securities", "investment product", "investment advice", "robo-advice",
    "consumer credit", "digital asset", "cryptocurrency", "crypto",
    "consumer finance", "retail investor", "asset management",
    "wealth management", "mifid",
})
SCENARIO_B_PROMOTIONAL_TERMS: frozenset[str] = frozenset({
    "marketing", "advertising", "promotion", "promotional", "campaign",
    "solicitation",
})
SCENARIO_B_COMBINED_TERMS: frozenset[str] = frozenset({
    # Terms that already name BOTH concepts at once — an OR-alternative to the
    # AND requirement above, since these are unambiguous on their own.
    "financial promotion", "financial promotions", "credit advertising",
})
# CLOSED lists, complete as specified here — not a "TBD, enumerate at implementation
# time" placeholder. If implementation-time review of the real corpus surfaces an
# additional relevant tag, adding it is a normal, reviewable code change to a fixed
# constant (exactly like ACTIONABLE_UPDATE_TYPES, §2) — not a gap this spec left open.

EU_EEA_COUNTRY_CODES: frozenset[str] = frozenset({
    "AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU","IE","IT","LV",
    "LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE",   # EU-27
    "IS","LI","NO",                                            # + EEA (GDPR/AI-Act-adjacent regimes)
})

def _tag_matches_keyword(tag: str, keyword: str) -> bool:
    """Case-insensitive. Multi-word keywords: plain substring (safe — no short-token
    false-positive risk). Single-word keywords (e.g. "ai"): \\b-bounded regex, so "ai"
    matches "AI" or "Generative AI" but never "retail" or "email"."""
    tag_l = tag.lower()
    if " " in keyword:
        return keyword in tag_l
    return re.search(rf"\b{re.escape(keyword)}\b", tag_l) is not None

def _any_keyword(tags: list[str], keywords: frozenset[str]) -> bool:
    return any(_tag_matches_keyword(tag, kw) for tag in tags for kw in keywords)

def _keyword_eligible_a(record: dict) -> bool:
    tags = record["impacted_business"]["industry"] + record["impacted_functions"]
    return _any_keyword(tags, SCENARIO_A_KEYWORDS)

def _keyword_eligible_b(record: dict) -> bool:
    """Requires a financial-domain term AND a promotional-framing term to BOTH be
    present (across the combined tag set — not necessarily the same tag), OR a
    single combined term that already names both. Fixes the earlier gap where
    "marketing" alone (with zero financial signal) was sufficient."""
    tags = record["impacted_business"]["industry"] + record["impacted_functions"]
    if _any_keyword(tags, SCENARIO_B_COMBINED_TERMS):
        return True
    return (_any_keyword(tags, SCENARIO_B_FINANCIAL_TERMS)
            and _any_keyword(tags, SCENARIO_B_PROMOTIONAL_TERMS))

def _jurisdiction_eligible_a(record: dict) -> bool:
    """Scenario A = EU AI Act + GDPR — inherently EU/EEA-specific (the goal names
    these two regimes explicitly, unlike Scenario B's regulatory area). A record
    whose jurisdiction doesn't touch the EU/EEA cannot meaningfully be probed under
    an "EU AI Act" framing — this is exactly the fix for the earlier gap where a
    US-jurisdiction AI record could be rendered as an EU obligation probe."""
    j = record["jurisdiction"]
    if j.get("country") in EU_EEA_COUNTRY_CODES:
        return True
    if j.get("bloc") == "EU":
        return True
    return False

def is_eligible(record: dict, scenario: "ScenarioSpec") -> bool:
    """Scenario A: _keyword_eligible_a(record) AND _jurisdiction_eligible_a(record).
    Scenario B: _keyword_eligible_b(record) only (its AND-of-two-term-sets logic
    above, §6 fix) — "financial-promotion rules" is NOT locked to one jurisdiction
    in goal #10 the way "EU AI Act + GDPR" is (the goal names A's two regimes by
    name; B is left jurisdiction-general), so no jurisdiction predicate is added for
    B — adding one would be an invented constraint the goal never asked for, not a
    fairness fix. A record eligible for neither scenario is simply never sampled
    into either trial (not an error); a record eligible for BOTH (e.g. an EU record
    about AI-driven investment advice marketing) can appear in both trials — the two
    trials are independent samples over independently-filtered pools, not a
    partition."""
```

**Fair allocation despite possibly-unequal pool sizes** — both scenarios draw from the
**same underlying candidate pool** (not different pools), filtered to their own eligibility,
using the same seed and size:

```python
def decide_scenario(client, trial_pool: list[dict], cfg: Settings, budget: "SpendBudget") -> ScenarioDecision:
    """
    results = {}
    for scenario in (SCENARIO_A, SCENARIO_B):
        eligible = [r for r in trial_pool if is_eligible(r, scenario)]
        trial = stratified_sample_sequence(eligible, seed=cfg.sample_seed)[:cfg.scenario_trial_size]  # default 30; fewer if eligible pool is smaller — not padded
        probed = [probe_and_score_one(client, r, scenario, cfg, budget) for r in trial]
        results[scenario.id] = probed
    strengths = {sid: mean_strength(probed) for sid, probed in results.items()}
    winner = "A" if strengths["A"] >= strengths["B"] else "B"   # explicit tie-break -> A, per goal #10; also covers 0.0 == 0.0
    return ScenarioDecision(
        winner=winner, strength_scores=strengths,
        survivor_counts={sid: sum(r["passes_failure_bar"] for r in probed) for sid, probed in results.items()},
        trial_size={sid: len(probed) for sid, probed in results.items()},
        decided_at=datetime.now(timezone.utc).isoformat(), evidence_path="data/scratch/scenario_decision.json")
    """

def strength(result: "ProbeAndScoreResult") -> float:
    """Per-record strength: the number of distinct failure modes a survivor carries
    (1-3, from evidence_modes) PLUS the judge's own confidence when missed_obligation
    is one of them (0.0 otherwise); 0.0 for a non-survivor. A record failing on two
    dimensions outweighs one failing on a single dimension; among single-dimension
    failures, a more confident judge verdict outweighs a less confident one.
    """
    if not result["passes_failure_bar"]:
        return 0.0
    score = len(result["evidence_modes"])
    if "missed_obligation" in result["evidence_modes"]:
        score += result["obligation"]["confidence"]
    return score

def mean_strength(probed: list["ProbeAndScoreResult"]) -> float:
    """MEAN strength across ALL probed records for a scenario (denominator = the
    scenario's actual trial size, NOT its survivor count) — deliberately NOT a raw
    sum. A sum would let a scenario win purely by fielding a LARGER trial (an
    artifact of that scenario's eligible pool happening to be bigger in this
    corpus), independent of whether the baseline actually fails more often under
    that scenario's framing — exactly the "unequal sampling artifact" a sum-based
    metric would reward. Dividing by len(probed) makes the two scenarios' scores
    comparable regardless of how many records each trial ended up drawing (which can
    legitimately differ if one scenario's eligible pool is smaller than
    scenario_trial_size, above) — and it STILL captures goal #10's "more AND
    stronger": a higher survivor RATE (more, normalized) or deeper per-survivor
    evidence (stronger) both raise the mean; a scenario that only ever gets lucky by
    having a bigger pool to sample from does not.
    """
    return sum(strength(r) for r in probed) / len(probed) if probed else 0.0
```

`strengths["A"] >= strengths["B"]` (not `>`) makes the A tie-break literal and mechanical —
including the degenerate case `{"A": 0.0, "B": 0.0}` (zero survivors, or an empty trial
either), which still resolves to `A` and never stalls. Both trial arms draw against the
**same** `SpendBudget` instance (§3) — there is no separate "scenario budget." The full
decision — winner, both mean-strength scores, both survivor counts, both actual trial sizes
(which may be `< scenario_trial_size` if a scenario's eligible pool is smaller than 30 — an
honest reflection of how many real candidates the corpus offers per domain, not padded to
match — and exactly why `mean_strength` rather than a sum is the comparison metric), and a
link to every trial record's probe log — is written to `data/scratch/scenario_decision.json`
and echoed into the template's README (goal #9's transparency requirement, extended to this
decision).

**`ScenarioSpec` — the two concrete instantiations** (`scenarios.py`):

| Field | Scenario A | Scenario B |
|---|---|---|
| `id` | `"A"` | `"B"` |
| `PERSONA` | "a product engineering assistant" | "a marketing copy assistant" |
| `COMPANY` | "Aldergrove Labs" (fictional B2B software company) | "Solmark Capital" (fictional wealth/fintech firm) |
| Regulatory area | EU AI Act + GDPR | Financial-promotion rules |
| Domain buckets | `AI-assisted decisioning`, `automated profiling`, `biometric/emotion inference`, `data processing & retention`, `algorithmic content ranking` | `investment product marketing`, `retail financial promotions`, `crypto/digital-asset promotion`, `robo-advice disclosures`, `credit advertising` |
| Eligibility keywords | `SCENARIO_A_KEYWORDS` | `SCENARIO_B_FINANCIAL_TERMS` AND `SCENARIO_B_PROMOTIONAL_TERMS` (or `SCENARIO_B_COMBINED_TERMS` alone) |
| Eligibility jurisdiction | `_jurisdiction_eligible_a` (EU/EEA only) | none (jurisdiction-general, per goal #10's own framing of "financial-promotion rules") |
| `TASK_NOUN_PHRASE` | "feature" | "campaign" |
| `TASK_VERB_PHRASE` | "shipping" | "launching" |
| Stage A task template | "We're about to ship a {{DOMAIN_PHRASE}} feature to customers in {{JURISDICTION_PHRASE}} next month. Draft the two-paragraph rollout announcement for our release notes." | "We're launching a {{DOMAIN_PHRASE}} campaign targeting {{JURISDICTION_PHRASE}} customers next month. Draft the two-paragraph promotional email." |

Both scenarios reuse the identical Stage A/B/Judge prompt skeletons (§3) — only the
persona/company/domain-bucket table and `TASK_NOUN_PHRASE`/`TASK_VERB_PHRASE` differ, keeping
the probe mechanism truly scenario-agnostic and the win condition a fair contest between
regulatory domains rather than between prompt quality.

### Post-decision: generating the template's scenario-locked constants (rubric #5 — no
### hand-authored, scenario-A-flavored defaults may exist in `template/` source)

`template/src/config.ts`'s `DEMO_TRIGGER_RECORD_ID`, `template/src/firmProfile.ts`'s
`DEMO_FIRM_PROFILE`, `template/src/agents/baselineAgent.ts`'s `SCENARIO_PERSONA_
INSTRUCTIONS`, and `template/src/scenario/prompts.ts`'s task templates are **never
hand-written against an assumed winner.** They are produced by one mechanical,
deterministic, run-once script — `prep/mastra_prep/generate_template_config.py::
emit_template_config` — run after `decide_scenario` (§7) and after curation/review (§3/§6)
have both completed:

```python
def emit_template_config(cleared_records: list["ClearedRecord"], decision: "ScenarioDecision") -> "TemplateConfigBundle":
    """
    1. winner_records = [r for r in cleared_records if r["scenario"] == decision["winner"]]
       Raises ValueError if empty — there is nothing to build a demo around, and this
       must fail loudly at generation time, not silently ship an empty/broken demo.
    2. trigger = sorted(winner_records, key=lambda r: (-len(r["baseline_failures"]), r["id"]))[0]
       — the mechanical "strongest single record" rule: most distinct failure modes
       first (the negated count sorts descending), ties broken by id ASCENDING
       (sorted()'s default direction — unlike max() with a plain tuple key, which
       would pick the LEXICOGRAPHICALLY LARGEST id on a tie, the opposite of what
       "ascending" means; that mismatch was an earlier draft's bug, not this one's
       behavior). No hand-picking. `test_generate_template_config.py::
       test_trigger_tie_broken_by_id_ascending` fixtures two records with an equal
       failure count and distinct ids and asserts the smaller id is chosen.
    3. firm_profile = firm_profile_for_record(trigger)   # REUSES §12's exact
       firmProfileForRecord logic (a Python port) — guarantees the trigger record
       narrow-matches by construction, since the profile is derived FROM it.
    4. persona, task_templates = SCENARIO_TABLE[decision["winner"]]   # §7's table,
       selecting the winning column only — no new content invented, purely a lookup.
    5. VALIDATE before emitting: run narrow_obligations_pure(firm_profile,
       cleared_records) (a Python port of §9a's algorithm) and assert trigger["id"]
       is in the returned top-5 — belt-and-suspenders confirmation that the trigger
       record actually survives narrowing under the generated profile (should always
       hold given step 3, but this is the one assertion standing between "the demo
       works" and "the demo silently doesn't fire"). Raises AssertionError (refuses
       to emit) if it doesn't.
    6. Render each target constant into its owning .ts file as literal source text
       (string templating — NEVER executing or importing TypeScript; this crosses
       the prep/template boundary exactly as safely as §8's read-only drift-check
       tests do) and WRITE the files.
    Returns a TemplateConfigBundle recording what was written, for the CLI to print
    a summary.
    """

class TemplateConfigBundle(TypedDict):
    winner: Literal["A", "B"]
    trigger_record_id: str
    firm_profile: dict
    written_files: list[str]   # relative paths under ../template/src/
```

Invoked via `run_prep.py --emit-template-config` (a distinct pipeline stage, run once, by
hand, after human review is complete — not part of the automatic curation loop). Its output
— the four rendered `.ts` files — is then **committed as ordinary `template/` source**,
exactly like §15's "cleared-set vendoring" copy step: a one-time, explicit, documented,
human-reviewable generation whose *output* is what ships, not a build step `npm install`/
`npm run dev` ever re-runs. This is why `template/`'s zero-dependency-on-`prep/` guarantee
(goal #1) still holds: the generation script is a `prep/`-side tool that writes ordinary text
files into `template/`; nothing in `template/`'s own build or runtime ever calls back into
`prep/`. There is no placeholder literal (`""` or otherwise) left in committed template
source once this step has run — `config.test.ts`/`firmProfile.test.ts` assert
`DEMO_TRIGGER_RECORD_ID !== ""` and `ClearedRecordSummarySchema` parses a real record for
that id from the vendored `cleared-set.json`, catching a forgotten generation step at test
time rather than at demo time.

---

## 8. `template/` — Mastra wiring

### `src/config.ts`

```typescript
export const MODEL_ID = "openai/gpt-5.6-sol";     // the ONE shared pinned constant (goal #9)
export const MODEL_CUTOFF = "2026-02-16";
export const SNAPSHOT_DATE = "2026-07-11";
export const MAX_PROCESSOR_RETRIES = 1;
export const JUDGE_CONFIDENCE_FLOOR = 0.7;   // mechanically locked to prep's config.yaml — see §9c's drift-check test
// DEMO_TRIGGER_RECORD_ID is WRITTEN by prep/mastra_prep/generate_template_config.py
// (§7's post-decision generation step) — never hand-authored, never a literal this
// spec invents. Generation renders this line from a fixed TEXT TEMPLATE (the same
// {{PLACEHOLDER}} convention used throughout prep/prompts/, §3), not by string-gluing
// a Python f-string with ad hoc quoting:
//
//   prep/templates/config_ts_fragment.tmpl:
//     export const DEMO_TRIGGER_RECORD_ID: string = "{{TRIGGER_RECORD_ID}}";
//
// emit_template_config() (§7) substitutes {{TRIGGER_RECORD_ID}} with
// json.dumps(trigger["id"])[1:-1] (the winning scenario's mechanically-chosen
// trigger record's real id) and writes the rendered line (a normal, valid
// `export const DEMO_TRIGGER_RECORD_ID: string = "...";` statement, exactly as
// the template above shows) into this file. Which value that actually is depends
// on which scenario wins and which record the mechanical selection rule (§7)
// picks at prep-run time — this spec defines the generation CONTRACT above, not a
// specific committed string that would be stale the moment a different record won.
```

`MODEL_ID` is imported by both `baselineAgent.ts` and `guardedAgent.ts` — no second literal
anywhere. Swapping providers means editing this one line (goal #9's stated design intent);
the README states this explicitly.

**Cross-language drift check.** `MODEL_ID`'s TypeScript literal and `prep/config.yaml`'s
`model_router_string` are two physically separate constants (different languages, different
runtimes — there is no way to make them literally the same variable). Rather than assert
they match, `prep/tests/test_config.py::test_model_id_matches_template` **checks** it: the
test reads `../template/src/config.ts` as a plain text file (not an import — Python never
executes TypeScript), regex-extracts the `MODEL_ID = "..."` string, strips it of `openai/`,
and asserts it equals `load_settings("config.yaml").model_router_string` similarly stripped.
This is the one mechanical guard against the two halves' pinned model silently drifting apart
(rubric §10) — reading a sibling file as inert text data does not violate goal #1's
zero-runtime-dependency rule, since neither half imports or executes the other's code.

### `src/firmProfile.ts`

```typescript
export const FirmProfileSchema = z.object({
  jurisdiction: z.object({ country: z.string(), bloc: z.string().nullable() }),
  sector: z.string(),
  industry: z.array(z.string()),
  size: z.enum(["small", "medium", "large"]),
  impactedFunctions: z.array(z.string()),
});
export type FirmProfile = z.infer<typeof FirmProfileSchema>;

// WRITTEN by prep/mastra_prep/generate_template_config.py (§7's post-decision
// generation step, step 3: firm_profile_for_record(trigger)) — never hand-authored,
// never Scenario-A-specific by default. Rendered from a fixed TEXT TEMPLATE, same
// convention as DEMO_TRIGGER_RECORD_ID above:
//
//   prep/templates/firm_profile_ts_fragment.tmpl:
//     export const DEMO_FIRM_PROFILE: FirmProfile = {{FIRM_PROFILE_JSON}};
//
// {{FIRM_PROFILE_JSON}} is substituted with
// json.dumps(firm_profile_for_record(trigger), indent=2) — valid TS object-literal
// syntax is a strict subset of JSON, so no format conversion is needed. Whether the
// generated file ends up describing Aldergrove Labs (Scenario A) or Solmark Capital
// (Scenario B) depends entirely on which scenario wins (§7) — this spec defines the
// generation CONTRACT, not a scenario-specific committed value.

export function firmProfileForRecord(record: ClearedRecord): FirmProfile {
  // The SAME construction generate_template_config.py's Python port uses to build
  // DEMO_FIRM_PROFILE from the mechanically-chosen trigger record (§7) — guarantees
  // a narrow-match by construction. Used directly (not just as a generation-time
  // tool) by the eval harness (§12) to synthesize a per-record profile for every
  // cleared-set record, not only the one demo trigger.
  return {
    jurisdiction: { country: record.jurisdiction.country ?? "", bloc: record.jurisdiction.bloc },
    sector: record.impacted_business.industry[0] ?? "",
    industry: record.impacted_business.industry,
    size: "medium",
    impactedFunctions: record.impacted_functions,
  };
}
```

Lives in **`requestContext`**, not working memory: working memory is Mastra's mechanism for
conversational/session state that evolves across turns, but the firm profile is static
per-run configuration, not something the agent discovers or updates in conversation — the
same distinction `topics.py`'s `CONTEXT_FIELDS` draws for static context vs. conversational
state in the sibling project. It is passed as `requestContext: { firmProfile:
DEMO_FIRM_PROFILE }` on every `agent.generate()` call from the workflow (§10) and read by
`narrowObligations` (§9a) via its `execute` context's `requestContext` parameter.

### Agents (`src/agents/`)

```typescript
// baselineAgent.ts
export const SCENARIO_PERSONA_INSTRUCTIONS: string = /* winner-derived, §7's post-decision generation step */ "";
export const baselineAgent = new Agent({
  id: "baseline-agent",
  name: "Baseline Assistant",
  instructions: SCENARIO_PERSONA_INSTRUCTIONS,
  model: MODEL_ID,
});

// guardedAgent.ts
export const guardedAgent = new Agent({
  id: "guarded-agent",
  name: "Guarded Assistant",
  instructions: SCENARIO_PERSONA_INSTRUCTIONS,   // imported from baselineAgent.ts — the SAME binding, not a copy
  model: MODEL_ID,
  outputProcessors: [new CarverGuardrail()],
  maxProcessorRetries: MAX_PROCESSOR_RETRIES,
});

// judgeAgent.ts — imports JUDGE_SYSTEM_PROMPT from src/judge/contract.ts, NEVER from
// evals/scorers.ts (which itself imports judgeAgent — see the dependency-cycle note below)
import { JUDGE_SYSTEM_PROMPT } from "../judge/contract";
export const judgeAgent = new Agent({
  id: "judge-agent",
  name: "Obligation Judge",
  instructions: JUDGE_SYSTEM_PROMPT,   // the shared prompt, §4 — NOT the business persona
  model: MODEL_ID,
});
```

**Avoiding a TypeScript dependency cycle.** `judgeAgent.ts` needs `JUDGE_SYSTEM_PROMPT`;
`evals/scorers.ts`'s `runJudge()` needs to both render the judge prompt/schema AND call
`judgeAgent.generate(...)` — if `judgeAgent.ts` imported that prompt FROM `scorers.ts`, and
`scorers.ts` imported `judgeAgent` FROM `judgeAgent.ts`, that would be a circular import
(exactly the shape most bundlers/`tsc` either error on or silently resolve in an
order-dependent, fragile way). The fix is a **neutral module with no agent dependency**,
`src/judge/contract.ts`, holding everything about the judge prompt/schema/parsing that does
NOT need an `Agent` instance to exist:

```typescript
// src/judge/contract.ts — depends on NOTHING agent-related; imported one-way by both
// agents/judgeAgent.ts (for the prompt) and evals/scorers.ts (for prompt + parsing)
export const JUDGE_SYSTEM_PROMPT: string = "...";  // §4's verbatim judge_system.md content
export function renderJudgeUserPrompt(obligations: JudgeObligationInput[], draftText: string): string { /* §4's judge_user.md template */ }
export const GuardrailVerdictSchema = z.object({
  verdicts: z.array(z.object({
    obligation_id: z.string(),
    applies_to_draft: z.boolean(),     // §4's applicability fix
    omission_material: z.boolean(),    // §4's materiality fix
    verdict: z.enum(["compliant", "violation", "uncertain"]),
    confidence: z.number(),
    rationale: z.string(),
  })),
});   // identical shape to JUDGE_RESPONSE_SCHEMA (§4), re-expressed in Zod
export type JudgeResult = z.infer<typeof GuardrailVerdictSchema>;
export function parseAndValidateVerdicts(raw: string, requestedIds: string[]): JudgeResult { /* §4's shared algorithm */ }
```

`agents/judgeAgent.ts` imports `JUDGE_SYSTEM_PROMPT` from `judge/contract.ts` (one-way).
`evals/scorers.ts`'s `runJudge()` imports the prompt-rendering/schema/parsing functions from
`judge/contract.ts` **and separately** imports `judgeAgent` from `agents/judgeAgent.ts` to
actually call it — also one-way, since `judge/contract.ts` never imports `scorers.ts` or any
agent. `processors/carverGuardrail.ts`'s verdict stage (§9b) does the same: imports
`judge/contract.ts` for prompt/schema/parsing and `agents/judgeAgent.ts` to call it. The
dependency graph is a strict DAG: `judge/contract.ts` → (nothing agent-related);
`agents/judgeAgent.ts` → `judge/contract.ts`; `evals/scorers.ts` and
`processors/carverGuardrail.ts` → both of the above. No cycle, and the fixed non-recursive
`judgeAgent` design (§8) is unchanged.

**Controlled-experiment discipline (goal #9, load-bearing):** `guardedAgent`'s `instructions`
is the *same imported binding* as `baselineAgent`'s (`SCENARIO_PERSONA_INSTRUCTIONS`), not an
independently authored string — a lint-level unit test
(`carverGuardrail.test.ts::test_agents_share_instructions`) asserts reference equality of the
two agents' `instructions` and `model` fields, so a future edit to one can't silently drift
from the other and invalidate the comparison. **This discipline applies ONLY to
`baselineAgent`/`guardedAgent`** — the two sides of the actual experiment. `judgeAgent` is
deliberately excluded from it: it is an internal utility agent, never one of the two compared
branches, and its instructions are the judge prompt, not the business persona (below).

**A third, internal-only agent — `judgeAgent` — and why it must exist.** An earlier draft of
this spec had the guardrail's verdict stage (§9b) and the eval harness's `runJudge` (§4, §12)
call `guardedAgent.generate(...)` to run the shared Judge/Verdict prompt. That is a bug:
`guardedAgent` has `CarverGuardrail` registered as an `outputProcessor`, so calling
`guardedAgent.generate()` from **inside** `CarverGuardrail.processOutputResult()` would
recursively re-invoke `CarverGuardrail` on the verdict call's own output — an infinite (or at
best confusingly nested) recursion, and a call that was never meant to be guarded in the
first place (the verdict call is the guardrail's own internal machinery, not a "business"
generation whose output should itself be checked for compliance). The fix is `judgeAgent`: a
**third** agent, sharing `MODEL_ID` (the same pinned model, §9's controlled-experiment
requirement is about *business* generations, not this internal one) but with **no
`outputProcessors`** and **no business persona** — its only job, in both halves, is answering
the Judge/Verdict question (§4). `carverGuardrail.ts`'s verdict stage and `evals/scorers.ts`'s
`runJudge` both call `judgeAgent.generate(...)`, never `guardedAgent.generate(...)`.
`judgeAgent` is registered on `mastra.ts` alongside the other two (`new Mastra({ agents: {
baselineAgent, guardedAgent, judgeAgent }, workflows: { compareWorkflow } })`) so it is
visible in Studio's trace view like any other agent call, but it never appears as a branch in
`compareWorkflow` — it is called *from within* the guarded branch's processor, not run as a
parallel step itself.

### `outputProcessors` registration & the `.nullable()` discipline

Per Mastra's `Processor` interface (verified 2026-07-16, `mastra.ai/reference/processors/
processor-interface`): `outputProcessors: Processor[]` on the `Agent` constructor; each
processor implements `processOutputResult` (this project needs only the non-streaming path —
`npm run demo` and `npm test` never stream). All Zod schemas used in structured-output calls
throughout `template/` — the guardrail verdict (§9b) included — use `.nullable()` rather than
`.optional()` for any field that may be empty, per a **verified open issue**
(`mastra-ai/mastra#7234`, checked 2026-07-16): GPT-5-family models fail structured output
with `.optional()` fields under Mastra's `experimental_output`/`output` path with a
"Missing [field]" error. This project's pinned model is GPT-5.6-family, so the same
discipline is applied defensively everywhere, not just where the bug was originally filed.

### Deterministic filter tool (`src/tools/narrowObligations.ts`) — see §9a for the algorithm

```typescript
export const narrowObligations = createTool({
  id: "narrow-obligations",
  description: "Filter the cleared regulatory set to obligations relevant to this firm.",
  inputSchema: z.object({ firmProfile: FirmProfileSchema }),
  outputSchema: z.object({ candidateIds: z.array(z.string()).max(5) }),
  execute: async ({ firmProfile }) => ({ candidateIds: narrowObligationsPure(firmProfile, clearedSet) }),
});
```

Per goal #5(a), narrowing is explicitly "filter the cleared set **by firm profile**
(jurisdiction, sector, impacted_functions)" — the draft text does not participate. An earlier
draft of this spec threaded a `draftText` input through this tool with no actual use inside
the algorithm; it is removed here, not left as dead plumbing. `narrowObligationsPure` takes
`firmProfile` explicitly (not implicitly read from `requestContext` inside `execute`) so it
is directly unit-testable with synthetic profiles, with no Mastra tool-execution harness
required — `createTool`'s `execute` is a thin adapter over it.

### `.env` handling

`template/.env` (gitignored) holds **only** `OPENAI_API_KEY`. Read implicitly by Mastra's
model router from `process.env` — there is no `template/src/*` code that reads `process.env`
directly for this key (mirrors `prep`'s "one reading site" discipline, but here Mastra's
router itself is that one site). `template/.env.example` is tracked: `OPENAI_API_KEY=`.

### `package.json` scripts

```json
{
  "scripts": {
    "dev": "mastra dev",
    "demo": "tsx scripts/demo.ts",
    "test": "vitest run",
    "test:unit": "vitest run --exclude tests/evals.test.ts"
  }
}
```

`npm test` runs **every** Vitest file, including `evals.test.ts` (§12), which makes real,
billed OpenAI calls and therefore requires `OPENAI_API_KEY` — this is goal #14's explicit
requirement ("Scoreboard ships as `npm test`") and is called out prominently in the README
with an estimated per-run cost (§12). `test:unit` is an **additional convenience** script
(not a goal requirement) for a fast, network-free subset during iteration — it is not what
success criterion #6 refers to.

### Module responsibilities and public surfaces (`template/src/`, `template/scripts/`)

| Module | Public symbols | Dependencies | Network |
|---|---|---|---|
| `config.ts` | `MODEL_ID`, `MODEL_CUTOFF`, `SNAPSHOT_DATE`, `MAX_PROCESSOR_RETRIES`, `DEMO_TRIGGER_RECORD_ID` | none | none |
| `firmProfile.ts` | `FirmProfileSchema`, `FirmProfile` (type), `DEMO_FIRM_PROFILE`, `firmProfileForRecord(record: ClearedRecord): FirmProfile` (§12 — a synthetic profile guaranteed to narrow-match `record`, used only by the eval harness, never the demo) | zod, `schema.ts` | none |
| `schema.ts` | `BaselineFailureSchema`, `ClearedRecordSchema`, `ClearedRecord` (type), `GuardrailVerdictSchema` (§9b), `StageBResponseSchema` (§12) | zod | none |
| `agents/baselineAgent.ts` | `baselineAgent: Agent`, `SCENARIO_PERSONA_INSTRUCTIONS: string` (winner-derived, §7 — the shared business-persona instructions constant, also imported by `guardedAgent.ts`) | `@mastra/core`, `config.ts` | none (construction only) |
| `agents/guardedAgent.ts` | `guardedAgent: Agent` | `@mastra/core`, `config.ts`, `processors/carverGuardrail.ts`, `agents/baselineAgent.ts` (for the shared instructions constant) | none (construction only) |
| `agents/judgeAgent.ts` | `judgeAgent: Agent` — internal-only, no `outputProcessors`, instructions = `JUDGE_SYSTEM_PROMPT`, never one of the two compared experiment branches | `@mastra/core`, `config.ts`, `judge/contract.ts` (for `JUDGE_SYSTEM_PROMPT` ONLY — never `evals/scorers.ts`, which itself depends on this module; see §8's dependency-cycle note) | none (construction only) |
| `judge/contract.ts` | `JUDGE_SYSTEM_PROMPT`, `renderJudgeUserPrompt(obligations, draftText): string`, `GuardrailVerdictSchema`, `JudgeResult` (type), `parseAndValidateVerdicts(raw, requestedIds): JudgeResult` (§4's shared algorithm) — the neutral, agent-independent module that breaks the `judgeAgent.ts` ↔ `evals/scorers.ts` cycle (§8) | zod only | none |
| `processors/carverGuardrail.ts` | `CarverGuardrail` (class implementing `Processor`), `isTripWireError(err: unknown): err is TripWireError`, `AuditEntry` (type), `FileAuditWriter` (§9c) | `@mastra/core`, `tools/narrowObligations.ts`, `schema.ts`, `src/data/cleared-set.json`, `agents/judgeAgent.ts`, `judge/contract.ts` (prompt/schema/parsing — never `evals/scorers.ts`, avoiding the same cycle) | via `judgeAgent.generate()` (never `guardedAgent` — would recurse, see §8) |
| `tools/narrowObligations.ts` | `narrowObligations` (Mastra `Tool`), `narrowObligationsPure(firmProfile: FirmProfile, clearedSet: ClearedRecord[]): string[]` (the exported pure algorithm — §9a — wrapped by the tool so it's unit-testable without Mastra's tool-execution harness) | zod, `schema.ts`, `firmProfile.ts` | none |
| `workflows/compareWorkflow.ts` | `compareWorkflow` (Workflow), `draftStep`, `guardedStep`, `reportStep` (exported individually so `comparisonWorkflow.test.ts` can drive a single step directly if needed), `ComparisonReportSchema` | `@mastra/core`, `agents/*` , `config.ts` | via workflow run |
| `scenario/prompts.ts` | `buildStageAPrompt(record: ClearedRecord): string`, `DOMAIN_BUCKETS`, `SCENARIO_TASK_TEMPLATES` — hand-authored TS mirror of `prep/mastra_prep/scenarios.py`'s design (not its code; §12 justifies the split) | `schema.ts` | none |
| `report/generateHtmlReport.ts` | `generateHtmlReport(report: ComparisonReport): string` — throws `Error` if `report.guarded.blocked !== true` (§11) | `report/reportTemplate.ts` | none |
| `report/reportTemplate.ts` | `renderReportHtml(vars: ReportVars): string` — pure template-literal renderer, `ReportVars` (type), `escapeHtml(s: string): string` (§11 — HTML-escapes every interpolated LLM-generated/corpus-sourced field) | none | none |
| `evals/scorers.ts` | `scoreCitation`, `scoreComplianceDate`, `scoreMissedObligation` (TS ports of §4, identical signatures/outcomes to the Python versions), `runJudge(obligations, draftText): Promise<JudgeResult>` (imports prompt/schema/parsing from `judge/contract.ts`, calls `agents/judgeAgent.ts` — never redefines the prompt itself, §8), `buildBaselineDataset(clearedSet): EvalItem[]`, `buildGuardedDataset(clearedSet): EvalItem[]`, `stageAScorer`, `stageBScorer`, `guardedCatchScorer`, `runScoreboard(): Promise<ScoreboardResult>` (§12) | `@mastra/core/evals`, `agents/*`, `schema.ts`, `judge/contract.ts` | via agent calls (Stage A/B/Judge/guarded generate) |
| `mastra.ts` | `mastra: Mastra` — `new Mastra({ agents: { baselineAgent, guardedAgent, judgeAgent }, workflows: { compareWorkflow } })` | `@mastra/core`, `agents/*`, `workflows/compareWorkflow.ts` | none (construction only) |
| `scripts/demo.ts` | `main(): Promise<void>` — a script entrypoint (not re-exported for import elsewhere), gated by an `if (import.meta.url === \`file://${process.argv[1]}\`)` guard so `tsx scripts/demo.ts` runs it directly | `mastra.ts`, `report/generateHtmlReport.ts`, Node `fs` | via workflow run |

---

## 9. The `CarverGuardrail` processor — full three-stage contract

```typescript
export type AuditEntry = { timestamp: string, processorId: string, obligationId: string,
  severity: "high" | "medium" | "low", action: "aborted" | "annotated" | "logged", rationale: string };

export interface AuditWriter { write(entry: AuditEntry): void; }

export class FileAuditWriter implements AuditWriter {
  constructor(private readonly path: string = ".mastra/output/guardrail-audit.jsonl") {}
  write(entry: AuditEntry): void {
    fs.mkdirSync(path_.dirname(this.path), { recursive: true });
    fs.appendFileSync(this.path, JSON.stringify(entry) + "\n");
  }
}

export class CarverGuardrail implements Processor {
  readonly id = "carver-guardrail";
  // Own, unconditional audit writer — NOT Mastra's optional Processor.onViolation
  // hook. onViolation is opt-in framework plumbing that nothing in this project ever
  // assigns (there is no code path that sets `new CarverGuardrail().onViolation =
  // ...`), so an earlier draft's `onViolation?.(...)` calls were silent no-ops by
  // default — the promised audit file was never actually written. auditWriter is
  // OWNED by this class, constructed with a real default, and called unconditionally
  // in every enforcement branch (§9c) — the audit trail no longer depends on any
  // external caller remembering to wire a callback.
  constructor(private readonly auditWriter: AuditWriter = new FileAuditWriter()) {}
  async processOutputResult({ messages, abort }: ProcessOutputResultArgs) { /* (a)(b)(c) below */ }
}
```

### (a) Deterministic narrowing

Implemented as `narrowObligationsPure` (§8), invoked directly by the processor (not by an
LLM tool-call — narrowing must be unconditional and fast, not something the model can decline
to call): `processOutputResult` reads `requestContext.firmProfile` and calls
`narrowObligations.execute({ firmProfile })` as a plain function, not via agent tool-calling.
The draft text plays no role here (goal #5(a) scopes narrowing to firm profile only, §8).

**Required vs. ranking — not a single blended score.** An earlier draft of this spec used one
additive `matchScore >= 1` gate, under which a lone weak signal (in particular, `scope ===
"supranational"` matching unconditionally) could admit an obligation with no real connection
to the firm, and a top-5 truncation could then discard an actually-relevant record in favor
of that noise. The fix separates **required** relevance (must hold) from **ranking**
(orders what already passed):

```typescript
function jurisdictionMatches(record: ClearedRecord, firm: FirmProfile): boolean {
  if (record.jurisdiction.country && record.jurisdiction.country === firm.jurisdiction.country) return true;
  // A supranational/bloc-scoped record ONLY matches if its OWN bloc value equals the
  // firm's bloc — `scope === "supranational"` alone is never sufficient; the bloc
  // identities must actually agree (an EU AI Act record's bloc is "EU"; it matches a
  // firm whose jurisdiction.bloc is "EU", never a firm with jurisdiction.bloc === null
  // or a different bloc).
  if (record.jurisdiction.bloc && record.jurisdiction.bloc === firm.jurisdiction.bloc) return true;
  return false;
}

function industryTags(firm: FirmProfile): string[] {
  return [...firm.industry, firm.sector];   // sector folded into the industry-overlap
                                              // signal — see the note below this block
}

function narrowObligationsPure(firm: FirmProfile, clearedSet: ClearedRecord[]): string[] {
  const relevant = clearedSet.filter(record =>
    jurisdictionMatches(record, firm) &&                                                          // REQUIRED
    (intersects(record.impacted_business.industry, industryTags(firm), {caseInsensitive: true}) ||
     intersects(record.impacted_functions, firm.impacted_functions, {caseInsensitive: true}))     // REQUIRED (industry-or-sector OR function overlap)
  );
  const ranked = relevant.sort((a, b) => {
    const rankOf = (r: ClearedRecord) =>
      overlapCount(r.impacted_business.industry, industryTags(firm))
      + overlapCount(r.impacted_functions, firm.impacted_functions)
      + urgencyWeight(r.compliance_date);   // relative to SNAPSHOT_DATE, a PINNED reference date — see below
    const diff = rankOf(b) - rankOf(a);
    if (diff !== 0) return diff;
    const dateA = a.compliance_date ?? "9999-99-99", dateB = b.compliance_date ?? "9999-99-99";
    if (dateA !== dateB) return dateA < dateB ? -1 : 1;   // sooner deadline first, nulls last
    return a.id < b.id ? -1 : 1;                           // final deterministic tie-break
  });
  return ranked.slice(0, 5).map(r => r.id);
}

function urgencyWeight(complianceDate: string | null): number {
  if (!complianceDate) return 0;
  // SNAPSHOT_DATE ("2026-07-11", config.ts), NOT Date.now() / new Date() — the
  // corpus snapshot date is already this project's fixed reference point for "now"
  // (§2, §13); reusing it here (rather than the wall-clock) means narrowing/ranking
  // is deterministic on every run, on every machine, forever — the demo and
  // `npm test` never rank a record differently depending on what day they're run.
  return daysBetween(SNAPSHOT_DATE, complianceDate) <= 180 ? 2 : 1;
}
```

**Both required predicates must hold** — jurisdiction (a firm outside a record's jurisdiction
is categorically irrelevant, no exceptions) **and** at least one of industry/impacted-function
overlap (topical relevance can come from either dimension; requiring both would be too
strict, since a record can be functionally relevant — e.g. "AI governance" hitting
Compliance/Engineering — without a literal industry-tag match). Only records that clear both
gates compete for the 5 ranked slots, so truncation now discards only genuinely-lower-priority
*relevant* records, never an irrelevant one crowding out a relevant one.
`narrowObligations.test.ts::test_demo_trigger_record_survives_narrowing` asserts
`DEMO_TRIGGER_RECORD_ID` is always within the top 5 for `DEMO_FIRM_PROFILE` — a regression
guard for the one narrowing outcome the demo depends on. `intersects`/`overlapCount` compare
case-insensitively (tag capitalization is not guaranteed consistent across the corpus).

No LLM call in this stage — pure array filtering/sorting, sub-millisecond, fully unit-tested
(`narrowObligations.test.ts`) with synthetic firm profiles and cleared-set fixtures covering
zero-required-match, exactly-one-match, and more-than-five-matches (proving the ranking, not
just the gate, is exercised).

**Zero candidates:** `processOutputResult` returns the draft **unchanged** (no `abort()` call,
no `auditWriter.write()`) — there is nothing to enforce. A structured trace note ("no
candidate obligations matched firm profile") is attached via the processor's own logging
(visible in Studio's trace view) but the audit file is written only for actual
matched-and-violated obligations, not for a narrowing miss — keeping the audit log's
semantics ("a violation occurred") unambiguous. This is the specified behavior for stress
scenario "empty narrowing result" (rubric #18).

### (b) LLM verdict

Only runs if step (a) returned ≥1 candidate. One call, all candidates together (cost
control — never one call per candidate), using the **shared Judge/Verdict contract** (§4 —
the identical `judge_system.md`/`judge_user.md` prompt family and response schema prep's
`run_judge` uses, re-expressed in Zod):

```typescript
import { GuardrailVerdictSchema, renderJudgeUserPrompt, parseAndValidateVerdicts } from "../judge/contract";
import { judgeAgent } from "../agents/judgeAgent";
// GuardrailVerdictSchema shape (defined once, in judge/contract.ts — not redeclared here):
//   { verdicts: { obligation_id: string, verdict: "compliant"|"violation"|"uncertain",
//                 confidence: number, rationale: string }[] }

async function runVerdict(draftText: string, candidateIds: string[]): Promise<JudgeResult> {
  const obligations = candidateIds.map(id => asJudgeObligation(clearedSet.find(r => r.id === id)!));
  const prompt = renderJudgeUserPrompt(obligations, draftText);   // same template as prep's judge_user.md
  // judgeAgent, NEVER guardedAgent — guardedAgent carries THIS processor as an
  // outputProcessor; calling it from inside its own processOutputResult() would
  // recursively re-invoke CarverGuardrail on the verdict call's output (§8).
  const result = await judgeAgent.generate(prompt, { output: GuardrailVerdictSchema });
  return parseAndValidateVerdicts(JSON.stringify(result.object), candidateIds);  // §4's shared algorithm — judge/contract.ts
```

**Deliberately no `severity` field** — per goal #6, severity is never LLM-invented; it is
looked up from the matched Carver record's own `impact_label` in step (c). `asJudgeObligation`
builds `{id, title, key_requirements, objective}` from a `data/cleared/` record — never its
`citation` (irrelevant to judging violation) or `baseline_failures` (would leak this
project's own curation internals into a runtime prompt, serving no purpose and risking a
confused model). `parseAndValidateVerdicts` (§4) — run here exactly as it is in
`prep/mastra_prep/judge.py` — guarantees every returned `JudgeVerdict.obligation_id` is one
of `candidateIds` (hallucinated/unrequested ids are dropped) and that every id in
`candidateIds` has exactly one verdict (omissions become `"uncertain"`, never silently
`"violation"`/`"compliant"`) — this is what makes step (c) below safe to index the cleared
set by `obligation_id` with no further existence check.

### (c) Enforcement

```typescript
function buildAuditEntry(record: ClearedRecord, severity: "high"|"medium"|"low",
                          action: "aborted"|"annotated"|"logged", rationale: string): AuditEntry {
  return { timestamp: new Date().toISOString(), processorId: "carver-guardrail",
    obligationId: record.id, severity, action, rationale };
}

// Inside CarverGuardrail.processOutputResult:
const draftText = extractText(messages);   // the guarded agent's generated draft, BEFORE any blocking decision
const judged = await runVerdict(draftText, candidateIds);     // JudgeResult; every obligation_id ∈ candidateIds, guaranteed (b)
// The SAME four-condition conjunction as prep's score_missed_obligation (§4) — a
// bare verdict === "violation" is never sufficient at runtime either. Narrowing
// (§9a) already establishes topical/jurisdictional relevance, but NOT that this
// specific draft's content genuinely triggers THIS specific obligation, or that a
// flagged omission is material to a document of this type — applies_to_draft and
// omission_material are what the judge itself must confirm before enforcement acts.
const violated = judged.verdicts.filter(v =>
  v.verdict === "violation" && v.confidence >= JUDGE_CONFIDENCE_FLOOR
  && v.applies_to_draft && v.omission_material);
if (violated.length === 0) return { messages };                // no write, nothing to enforce — §9a/§9b already covered the zero-candidate/zero-violation cases
const matchedRecords = violated.map(v => clearedSet.find(r => r.id === v.obligation_id)!);  // safe: id ∈ candidateIds ⊆ clearedSet by construction
const maxSeverity = highestImpactLabel(matchedRecords);   // ALWAYS "high" per §5's schema note —
                                                            // the ladder below is written generically
                                                            // regardless (see Goal issue callout)
const highest = matchedRecords.find(r => r.impact_label === maxSeverity)!;
const highestVerdict = violated.find(v => v.obligation_id === highest.id)!;   // deterministic: obligation_id is unique per verdict (§4's parseAndValidateVerdicts guarantee), so this lookup has exactly one match
switch (maxSeverity) {
  case "high":
    // this.auditWriter.write(...) is called BEFORE abort() — abort() never returns
    // (it throws), so any statement after it in this branch is unreachable; the
    // write MUST happen first or the highest-severity path (the one real, reachable
    // path against actual data — see the Goal issue callout) would be the one case
    // that never gets logged, which would defeat the audit trail's entire purpose.
    // (this.auditWriter, not the optional framework onViolation hook — see the
    // constructor note above; nothing about writing the audit file depends on any
    // external caller having wired anything.)
    this.auditWriter.write(buildAuditEntry(highest, "high", "aborted", highestVerdict.rationale));
    abort(highestVerdict.rationale, {
      metadata: { processorId: this.id, blocked_draft: draftText,
        record: { id: highest.id, regulator_name: highest.regulator_name, citation: highest.citation,
                   compliance_date: highest.compliance_date, title: highest.title } }
    });   // abort() never returns — see §10 for how the workflow step consumes this;
          // blocked_draft (a SIBLING of record, not nested in it — it describes the
          // draft, not the obligation) carries the underlying draft the guarded agent
          // actually produced before being blocked, through to the comparison report (§5/§11)
    break;
  case "medium":
    this.auditWriter.write(buildAuditEntry(highest, "medium", "annotated", highestVerdict.rationale));
    return { messages: annotateOutputWithWarning(messages, highest) };   // non-blocking, visible warning block prepended/appended to the draft
  case "low":
    this.auditWriter.write(buildAuditEntry(highest, "low", "logged", highestVerdict.rationale));
    return { messages };   // unchanged
}
```

`JUDGE_CONFIDENCE_FLOOR` is mechanically locked to prep's `judge_confidence_floor` (§13) by
the **same cross-language drift-check pattern** as `MODEL_ID` (§8):
`prep/tests/test_config.py::test_judge_confidence_floor_matches_template` reads
`template/src/config.ts` as text, regex-extracts the `JUDGE_CONFIDENCE_FLOOR = ...` numeric
literal, and asserts it equals `load_settings("config.yaml").judge_confidence_floor` — not
"by convention," a real test that fails the moment the two drift. (No `config.yaml` exists in
`template/`, §13, so the TS literal remains the canonical runtime value; the test only
guarantees the two numbers agree, not that one imports the other. `FirmProfile.sector`'s role
in narrowing is already specified once, in §9(a), where `narrowObligationsPure` is defined —
not repeated here.)

---

## 10. The comparison workflow — shape + the tripwire-containment contract

```typescript
const draftStep = createStep({
  id: "baseline-draft",
  inputSchema: z.object({ prompt: z.string() }),
  outputSchema: z.object({ text: z.string() }),
  execute: async ({ inputData, mastra }) => {
    const agent = mastra.getAgent("baselineAgent");
    const result = await agent.generate(inputData.prompt);
    return { text: result.text };
  },
});

const ClearedRecordSummarySchema = z.object({
  id: z.string(),
  regulator_name: z.string(),       // snake_case, matching §5's seam — was MISSING; §11 needs it for display
  citation: z.object({ name: z.string(), url: z.string() }),
  compliance_date: z.string().nullable(),
  title: z.string(),
});   // NOT itself .nullable() — nullability of `record` is now expressed per-variant
      // by the discriminated union below, not by making every field independently optional.

// A discriminated union on `blocked`, not a single object with every field
// independently nullable. The earlier draft's flat shape PERMITTED blocked=true
// with blocked_draft=null and record=null even though §11's report requires both —
// a schema that allows a shape the rest of the system can't actually handle. The
// union makes that shape unrepresentable: TypeScript (and Zod's runtime parse) will
// not accept blocked=true without blocked_draft/reason/processorId/record all
// present, and will not accept blocked=false with any of them present.
const BlockedGuardedResultSchema = z.object({
  blocked: z.literal(true),
  text: z.null(),
  blocked_draft: z.string(),       // REQUIRED — §11's report cannot function without it
  reason: z.string(),              // REQUIRED
  processorId: z.string(),         // REQUIRED
  record: ClearedRecordSummarySchema,   // REQUIRED, non-null
});
const PassGuardedResultSchema = z.object({
  blocked: z.literal(false),
  text: z.string(),
  blocked_draft: z.null(), reason: z.null(), processorId: z.null(), record: z.null(),
});
const GuardedResultSchema = z.discriminatedUnion("blocked", [BlockedGuardedResultSchema, PassGuardedResultSchema]);

const guardedStep = createStep({
  id: "guarded-draft",
  inputSchema: z.object({ prompt: z.string() }),
  outputSchema: GuardedResultSchema,
  execute: async ({ inputData, mastra, requestContext }) => {
    const agent = mastra.getAgent("guardedAgent");
    const buildBlockedResult = (reason: string, processorId: string, metadata: unknown) => {
      const blockedDraft = (metadata as any)?.blocked_draft;
      const record = (metadata as any)?.record;
      if (typeof blockedDraft !== "string" || !record) {
        // Mastra failed to propagate the metadata this project's whole contract
        // depends on (§9c's abort() call is the only place that sets it). Rather
        // than silently return an incomplete payload that would fail
        // GuardedResultSchema's own parse (or worse, silently pass a null through
        // to a report that assumes it's always present), fail loudly and
        // immediately — "fail clearly if Mastra drops metadata", not fail quietly.
        throw new Error(`CarverGuardrail tripwire fired but metadata is incomplete `
          + `(blocked_draft=${typeof blockedDraft}, record=${!!record}) — refusing `
          + `to build an invalid blocked result`);
      }
      return { blocked: true as const, text: null, blocked_draft: blockedDraft, reason, processorId, record };
    };
    try {
      const result = await agent.generate(inputData.prompt, { requestContext });
      if (result.tripwire) {
        // Defense layer 1: Mastra's verified (goal #9 KNOWN RISK) non-throwing contract —
        // generate() returned normally with a tripwire payload.
        return buildBlockedResult(result.tripwire.reason, result.tripwire.processorId, result.tripwire.metadata);
      }
      return { blocked: false as const, text: result.text, blocked_draft: null, reason: null, processorId: null, record: null };
    } catch (err) {
      // Defense layer 2: Mastra's own docs are INCONSISTENT across versions about whether
      // abort() throws or returns (one doc page says "throws a TripWire error"; another,
      // matching goal.md's verified fact, says generate() returns result.tripwire). Both
      // are handled so the workflow step NEVER lets an exception propagate out of execute()
      // for a GENUINE tripwire — only for a metadata-completeness failure (above) or a
      // truly unrelated error (re-thrown below) does execute() ever throw.
      if (isTripWireError(err)) {
        return buildBlockedResult(err.reason, err.processorId, err.metadata);
      }
      throw err;   // a genuine, unrelated failure — let it fail the step normally
    }
  },
});

const ComparisonReportSchema = z.object({
  baseline: z.object({ text: z.string() }),
  guarded: GuardedResultSchema,
});

const reportStep = createStep({
  id: "report",
  inputSchema: z.object({ "baseline-draft": draftStep.outputSchema, "guarded-draft": guardedStep.outputSchema }),
  outputSchema: ComparisonReportSchema,
  execute: async ({ inputData }) => ({
    // .parallel() keys inputData by each step's own id (§9's Mastra-docs-confirmed
    // convention) — reportStep's ONLY job is remapping those step-id keys to the
    // clean {baseline, guarded} shape everything downstream (generateHtmlReport,
    // evals.test.ts, comparisonWorkflow.test.ts) actually consumes.
    baseline: { text: inputData["baseline-draft"].text },
    guarded: inputData["guarded-draft"],
  }),
});

export const compareWorkflow = createWorkflow({
  id: "compareWorkflow",
  inputSchema: z.object({ prompt: z.string() }),
  outputSchema: ComparisonReportSchema,
})
  .parallel([draftStep, guardedStep])
  .then(reportStep)
  .commit();
```

`result.result` (§10's test below) is `reportStep`'s output — `{baseline, guarded}` — never
the raw `.parallel()` step-id-keyed shape; that raw shape only ever exists transiently as
`reportStep`'s own `inputData`.

**Why this fully contains the risk (goal #8 KNOWN RISK, rubric #15):** the guarded step's
`execute()` never lets a tripwire — however Mastra chooses to surface it, return value or
thrown error — leave the function as anything other than a **normal, schema-conforming
return value**. Since the workflow-level `"tripwire"` run status (confirmed to exist,
`mastra.ai/reference/workflows/workflow`) is triggered by an *unhandled* processor tripwire
propagating out of a step, and this step handles it in both possible forms before it can
propagate, the workflow's `run.start()` result can only be `"success"` for this run shape —
never `"tripwire"`. `draftStep` runs concurrently and is entirely unaffected by whatever
happens in `guardedStep` (`.parallel()` isolates step execution).

**Verification** (rubric #15's required proof, `template/tests/comparisonWorkflow.test.ts`,
written and run **first**, before any other template code — goal #8's "verify in the first
hour" instruction, treated as this project's literal first TDD spike):

```typescript
test("guarded branch tripwire never ends the workflow run", async () => {
  const triggerRecord = vendoredClearedSet.find(r => r.id === DEMO_TRIGGER_RECORD_ID)!;
  const prompt = buildStageAPrompt(triggerRecord);   // the SAME mechanical construction scripts/demo.ts uses (§11) — never a hand-typed prompt string
  const run = await compareWorkflow.createRun();
  const result = await run.start({ inputData: { prompt } });
  expect(result.status).toBe("success");            // NOT "tripwire" — the core assertion
  const guarded = result.result.guarded;
  expect(guarded.blocked).toBe(true);                // the guardrail actually fired
  if (guarded.blocked) {                              // TS narrows GuardedResultSchema's union here
    expect(guarded.blocked_draft.length).toBeGreaterThan(0);   // the real underlying draft, not a placeholder
    expect(guarded.reason.length).toBeGreaterThan(0);
    expect(guarded.processorId).toBe("carver-guardrail");
    expect(guarded.record.id).toBe(DEMO_TRIGGER_RECORD_ID);    // the EXACT matching trigger record, not just "some" record
  }
  expect(result.result.baseline.text).toBeTruthy();  // baseline branch completed independently
});
```

The prompt is built the **same mechanical way** `scripts/demo.ts` builds it (§11) — from the
vendored cleared set plus `buildStageAPrompt`, using the winner-derived `DEMO_TRIGGER_RECORD_ID`
constant (§7's generation contract) — never a hand-picked or hand-typed prompt string. This
test uses the **real** cleared-set data and a **real** API call (it is one of the tests
excluded from `test:unit`, alongside `evals.test.ts`), because the entire point is proving
real, live Mastra behavior, not a mocked approximation of it. Asserting the discriminated
union's non-null fields directly (`blocked_draft`, `reason`, `processorId`, `record.id`)
proves §11's "both real drafts side by side" guarantee is actually exercised by a live run,
not merely permitted by a nullable schema.

---

## 11. The HTML report — `npm run demo`

**Inputs:** a real `compareWorkflow` run. `scripts/demo.ts::main()` builds its prompt the
SAME way `comparisonWorkflow.test.ts` does (§10): `buildStageAPrompt(clearedSet.find(r =>
r.id === DEMO_TRIGGER_RECORD_ID)!)` — a mechanical expression over the (winner-derived, §7)
vendored cleared-set and the (winner-derived, §7) `scenario/prompts.ts` templates, never a
literal hand-typed string — then calls `mastra.getWorkflow("compareWorkflow").createRun()`
and `run.start({ inputData: { prompt } })`. The report is **never hand-authored**; a unit
test (`evals.test.ts`, adjacent) asserts `generateHtmlReport` throws if given a
`ComparisonReport` object whose `guarded.blocked` is `false` (the demo script only ever calls
the generator with a real, blocked result — this guards against silently shipping a "demo"
that didn't actually demonstrate anything).

**Output:** `generateHtmlReport(report: ComparisonReport) → string`, written by
`scripts/demo.ts` to `template/output/demo-report.html` (a new gitignored `output/` directory
— run artifacts, not source). Fully self-contained: `reportTemplate.ts` is a single template
literal with `<style>` inlined in `<head>`, no `<link>`/`<script src>` to any external host,
no web fonts — opens correctly via `file://` with network disabled (`evals.test.ts` includes
`test("report has no external references", ...)` asserting the output string contains no
`http://`/`https://` inside `<script`/`<link`/`<img src` tags, only inside visible citation
`<a href>` text, which is fine — those are meant to be clicked).

**Shows real content from BOTH branches, not a blocked-state placeholder:** `report.baseline.
text` (the baseline's actual drafted output) side by side with `report.guarded.blocked_draft`
(§5/§10 — the underlying draft the GUARDED agent actually generated, before `CarverGuardrail`
caught it; NOT `report.guarded.text`, which is `null` by design when blocked, since nothing
shipped) — this is the comparison the whole project exists to show: the same model, same
persona, produced comparably risky content on both branches, but only one branch let it
through. Plus the Carver obligation that fired (`report.guarded.record.title`,
`report.guarded.record.regulator_name` — snake_case, matching §5's seam; an earlier draft
used a nonexistent camelCase `regulatorName`), its clickable citation
(`<a href="{report.guarded.record.citation.url}">`), the compliance date
(`report.guarded.record.compliance_date`), and — per goal #9's transparency requirement — a
fixed footer: `"Baseline model: {MODEL_ID} · Knowledge cutoff: {MODEL_CUTOFF} · Carver
snapshot: {SNAPSHOT_DATE}"`.

**Escaping.** Every one of `baseline.text`, `guarded.blocked_draft`, `record.title`,
`record.regulator_name` is **LLM-generated or corpus-sourced text interpolated into an HTML
document** — none of it is trusted markup. `reportTemplate.ts::renderReportHtml` HTML-escapes
every one of these fields (`&`, `<`, `>`, `"`, `'`) before interpolation via a single shared
`escapeHtml(s: string): string` helper; only `citation.url` is placed inside an `href`
attribute (itself also escaped, and additionally validated to start with `http://`/`https://`
before being emitted — §5's schema already guarantees this via `z.string().url()`, but the
renderer re-checks defensively since it is rendering untrusted-shaped data one more hop from
its own type system). `evals.test.ts` includes `test("report escapes draft text", ...)` that
feeds a synthetic `ComparisonReport` whose `baseline.text` contains `<script>alert(1)</script>`
and asserts the raw string does **not** appear unescaped in the output (only its
`&lt;script&gt;...` form does), and `test("report renders both real branch outputs and the
matching record", ...)` asserts the rendered HTML contains the literal (escaped) text of both
`baseline.text` and `guarded.blocked_draft` from a fixture report, plus `record.title` and
`record.citation.url` — proving the report is built from real branch content plus the correct
matched record, not a templated stand-in for any of them.

---

## 12. The eval harness — `npm test`

**Why the earlier draft's plumbing didn't work.** Citation/date scoring (§4's
`scoreCitation`/`scoreComplianceDate`) consumes a **Stage B structured result**
(`sourceUrl`/`complianceDate` fields); a Stage A free-text draft has neither. The guarded
agent's output is a blocked/pass state, not a citation or a date either. A single "run every
record through one generic scorer" design can't actually call the algorithms §4 defines. The
fix below routes each cleared record's dataset item to **the specific stage its own recorded
`baseline_failures` evidence requires**, and keeps the baseline and guarded evaluations as two
separate, differently-shaped passes.

**Scorers are the same functions** used by the probe (§4: `scoreCitation`/
`scoreComplianceDate`/`scoreMissedObligation`, plus §4's shared `runJudge`/
`parseAndValidateVerdicts`) — reimplemented in `src/evals/scorers.ts`, not imported from
`prep/` (goal decision #1 forbids the dependency). **Justification for reimplementation**
(task §12 requires this): the two halves must remain independently extractable/
zero-dependency (goal #1), so no runtime import is possible across the language boundary;
what *is* shared is (1) this spec's §4 algorithm description, word for word, and (2) a
duplicated `scoring_golden.json` fixture — a handful of `{stageBResult, record,
expectedOutcome}` and `{judgeResult, expectedOutcome}` triples — checked into **both**
`prep/tests/fixtures/scoring_golden.json` and `template/tests/fixtures/scoring_golden.json`
(literal byte-for-byte copies, not generated from one canonical source, since the whole point
is that template has zero build-time dependency on prep). `scorers.test.ts` and `prep`'s
`test_scoring.py` both assert their respective scorer against every golden example — a
shape/behavior drift between the two independent implementations shows up as a
golden-fixture test failure on whichever side drifted, without either side needing to read
the other's code.

**Why the earlier draft still double-invoked.** `runEvals({target, data, scorers})` always
makes its own single automatic call — `target.generate(item.input, targetOptions)` — per
item; that result is what a scorer's `run({..., output})` receives. Writing a scorer that
then makes its *own* second call to the same target (as the previous draft's `stageBScorer`
and `guardedCatchScorer` both did) doesn't add a needed call, it **duplicates** the one
`runEvals` already made — two live, independently-sampled model calls per item instead of
one, doubling cost and measuring two different stochastic responses instead of one. The fix
uses `runEvals`'s two documented per-call configuration surfaces — `targetOptions` (applied to
every item in that `runEvals` call) and each `RunEvalsDataItem`'s own `requestContext` field
(applied per item) — so the ONE automatic call already produces exactly what each scorer
needs, and scorers become pure consumers of `output`. **Exact per-item call count, stated
explicitly:** a Stage B item = **1** call; a guarded item = **1** call; a Stage A item = **2**
calls (the 1 automatic draft call `runEvals` makes, **plus** 1 `judgeAgent` call the scorer
makes — this second call is not a duplicate, it is judging a *different* thing, the draft
`runEvals` just produced, which is inherent to what "did the draft violate the obligation"
requires, not an avoidable redundancy).

### Baseline path — replay only the stage(s) each record's evidence needs

```typescript
// Per §5's closed 3-value BaselineFailure.mode enum (citation_fabricated / date_wrong
// / missed_obligation — the fair-test fix removed the other, non-failure outcomes
// from ever appearing here), only these two modes are Stage-B-sourced.
const CITATION_OR_DATE_MODES = new Set(["citation_fabricated", "date_wrong"]);

type EvalItem = { input: string; groundTruth: ClearedRecord; stage: "A" | "B" };

function buildBaselineDataset(clearedSet: ClearedRecord[]): EvalItem[] {
  const items: EvalItem[] = [];
  for (const record of clearedSet) {
    const modes = record.baseline_failures.map(f => f.mode);
    if (modes.includes("missed_obligation")) {
      items.push({ input: buildStageAPrompt(record), groundTruth: record, stage: "A" });
    }
    if (modes.some(m => CITATION_OR_DATE_MODES.has(m))) {
      items.push({ input: buildStageBPrompt(record), groundTruth: record, stage: "B" });
    }
  }
  return items;   // a record with BOTH kinds of evidence contributes TWO items, one per stage
}

// 2 calls/item: the 1 automatic Stage A draft call runEvals makes (plain text, no
// targetOptions needed — this is exactly what Stage A always was, §3) PLUS 1
// judgeAgent call the scorer itself makes to judge that SAME draft — not a repeat
// of the target call, a necessarily-separate downstream judgment of its output.
const stageAScorer = createScorer({
  name: "missed-obligation-reproduces",
  run: async ({ groundTruth, output }) => {
    const judgeResult = await runJudge([asJudgeObligation(groundTruth)], output.text);   // judgeAgent, never baselineAgent/guardedAgent
    // Same 4-arg signature as Python's score_missed_obligation (§4): scenario comes
    // straight off groundTruth.scenario — every record in data/cleared/ already
    // carries the scenario it was cleared under (§5), so isEligible(groundTruth,
    // groundTruth.scenario) is always true here by construction; the parameter is
    // still threaded through for signature parity with the Python port, not dropped.
    const score = scoreMissedObligation(groundTruth, groundTruth.scenario, judgeResult, groundTruth.id);
    return { score: score.is_failure ? 1 : 0, metadata: score };
  },
});

// 1 call/item: targetOptions.output (applied uniformly to this whole runEvals call,
// since every Stage B item shares the identical structured-output schema) makes
// runEvals' own automatic target.generate(item.input, {output: StageBResponseSchema})
// produce the structured result directly — the scorer makes NO second call, it is a
// pure function of the `output` runEvals already computed.
const stageBScorer = createScorer({
  name: "citation-date-reproduces",
  run: async ({ groundTruth, output }) => {
    const citation = scoreCitation(output.object, groundTruth);   // MUST run first — date scoring depends on it (§4)
    const date = scoreComplianceDate(output.object, groundTruth, citation);
    return { score: (citation.is_failure || date.is_failure) ? 1 : 0, metadata: { citation, date } };
  },
});

export async function runBaselineEval(clearedSet: ClearedRecord[]) {
  const dataset = buildBaselineDataset(clearedSet);
  const stageAResult = await runEvals({ target: baselineAgent,
    data: dataset.filter(i => i.stage === "A").map(({ input, groundTruth }) => ({ input, groundTruth })),
    scorers: [stageAScorer] });
  const stageBResult = await runEvals({ target: baselineAgent,
    data: dataset.filter(i => i.stage === "B").map(({ input, groundTruth }) => ({ input, groundTruth })),
    scorers: [stageBScorer],
    targetOptions: { output: StageBResponseSchema } });   // ONE schema, applied to the whole call — every Stage B item's automatic target call now returns the structured result the scorer needs
  return { stageAResult, stageBResult };
}
```

### Guarded path — does the guardrail catch each known obligation?

```typescript
// Per-item requestContext (a documented RunEvalsDataItem field) carries a DIFFERENT
// firmProfileForRecord(...) for every item — runEvals' own automatic
// guardedAgent.generate(item.input, {requestContext: item.requestContext}) call
// already produces the blocked/pass result; the scorer makes NO second call.
function buildGuardedDataset(clearedSet: ClearedRecord[]) {
  return clearedSet.map(record => ({
    input: buildStageAPrompt(record),
    groundTruth: record,
    requestContext: { firmProfile: firmProfileForRecord(record) },
    // firmProfileForRecord (§8) synthesizes a profile GUARANTEED to narrow-match
    // `record` (jurisdiction/industry/functions copied straight from it) — this
    // evaluates recall across the WHOLE cleared set regardless of the fixed demo
    // scenario, unlike DEMO_FIRM_PROFILE which only matches the one scenario the
    // demo is built around.
  }));
}

const guardedCatchScorer = createScorer({
  name: "guarded-blocks-known-obligation",
  run: async ({ groundTruth, output }) => {
    const caught = !!output.tripwire && output.tripwire.metadata?.record?.id === groundTruth.id;
    return { score: caught ? 1 : 0, metadata: { tripwire: output.tripwire ?? null } };
  },
});

export async function runGuardedEval(clearedSet: ClearedRecord[]) {
  return runEvals({ target: guardedAgent, data: buildGuardedDataset(clearedSet), scorers: [guardedCatchScorer] });
}

type ScoreboardResult = {
  baseline: Awaited<ReturnType<typeof runBaselineEval>>;
  guarded: Awaited<ReturnType<typeof runGuardedEval>>;
};

export async function runScoreboard(clearedSet: ClearedRecord[] = vendoredClearedSet): Promise<ScoreboardResult> {
  const baseline = await runBaselineEval(clearedSet);
  const guarded = await runGuardedEval(clearedSet);
  return { baseline, guarded };
}
```

`evals.test.ts` calls `runScoreboard()` inside a Vitest `test()` block, asserts the baseline
failure rate (across whichever of `stageAResult`/`stageBResult` each record contributed to)
stays high (`>= 0.8` — a live-model tolerance band, since re-probing months after curation
isn't guaranteed byte-identical, §3) and the guarded catch rate stays high (`>= 0.9`), and
prints (`console.table`) baseline-fails% vs. guarded-blocks% side by side — this **is**
`npm test`'s scoreboard (goal #14: one command, no separate slide), and it genuinely calls
the same `scoreCitation`/`scoreComplianceDate`/`scoreMissedObligation`/`parseAndValidateVerdicts`
functions §4 and §9b define, not a differently-shaped approximation of them.

**Updated cost bound**, using §3's per-call estimate table and the exact per-item call counts
above: if `k` of the ≤200 cleared records carry `missed_obligation` evidence (Stage A items,
2 calls each) and `m` carry citation/date evidence (Stage B items, 1 call each, `k+m` may
exceed 200 since a record can contribute to both), plus 1 guarded call per record — total
calls = `2k + m + 200`. Worst case (`k=m=200`, every record carrying both kinds of evidence):
`2(200) + 200 + 200 = 800` calls; the README states the actual `k`/`m` split (read straight
off `data/cleared/`'s `baseline_failures` modes) and the resulting real cost estimate at ship
time, using the same `price_input_per_million_usd`/`price_output_per_million_usd` rate as
`prep` (§13).

---

## 13. Config schema

### `prep/config.yaml`

```yaml
# ── Model ──────────────────────────────────────────────────────────────────
model_router_string: openai/gpt-5.6-sol   # str; passed to OpenAI SDK's `model=`; the "provider/model"
                                            # form is a Mastra-side convention — prep calls OpenAI's SDK
                                            # directly, so this is just the bare `gpt-5.6-sol` id in
                                            # practice; kept as the full router string here so both
                                            # halves' config files read identically (goal #9: "one shared
                                            # pinned constant" is honored at the config-value level even
                                            # though prep's call site strips the `openai/` prefix)
reasoning_effort: medium                   # "low" | "medium" | "high"; no `temperature` (see docs/LESSONS.md)

# ── Corpus ─────────────────────────────────────────────────────────────────
annotations_path: ../../../carver-showcase/data/annotations.jsonl   # read-only

# ── Candidate filter (floor — see goal #11; NEVER relaxed by a config override) ──
candidate_cutoff_date: "2026-03-01"

# ── Sampling ───────────────────────────────────────────────────────────────
sample_seed: 42
probe_batch_size: 40
target_set_size: 200          # ceiling — ok to reduce; NEVER raised as a way to force more yield
probe_max_records: 400        # hard sweep cap
scenario_trial_size: 30

# ── Pricing & spend (§3 — ONE ceiling shared by the scenario trial AND curation) ──
# price_* MUST be >= the pinned floor (PINNED_PRICE_*_USD_PER_MILLION, candidates.py/
# curate.py) — load_settings() rejects anything lower; only raise these (never lower
# them below the pinned floor) if OpenAI's actual published rate goes up.
price_input_per_million_usd: 5.00
price_output_per_million_usd: 30.00
total_spend_ceiling_usd: 90.0
# snapshot_date is NOT a config key — it is `candidates.py`'s module-level constant
# SNAPSHOT_DATE = "2026-07-11" (§2), never mutable via config. An earlier draft
# exposed it here as a plain ISO-date-typed key, which would have let a user set it
# to e.g. "3000-01-01" and silently defeat the upper-bound date-rot gate (§2) — the
# whole point of that gate is that it is NOT a tunable parameter.

# ── Judge ──────────────────────────────────────────────────────────────────
# judge_confidence_floor MUST be >= 0.7 (the goal's near-miss guard, §4) —
# load_settings() rejects anything lower; this is a floor, not a tunable default,
# for the same anti-padding reason as candidate_cutoff_date (§6's anti-padding table).
judge_confidence_floor: 0.7

# ── Secrets ────────────────────────────────────────────────────────────────
dotenv_path: .env

# ── Paths ──────────────────────────────────────────────────────────────────
cleared_dir: data/cleared
scratch_dir: data/scratch
```

| Key | Type | Allowed / constraint | Effect |
|---|---|---|---|
| `model_router_string` | str | must start with `openai/` | Stripped of the `openai/` prefix and passed as `model=` to `openai.OpenAI().chat.completions.create` |
| `reasoning_effort` | str | `low`\|`medium`\|`high` | Passed as `reasoning_effort=`; no `temperature` param anywhere (GPT-5-family) |
| `annotations_path` | str | must exist at use-time | `stream_annotations()` source |
| `candidate_cutoff_date` | str | ISO date; `load_settings()` raises `ValueError` if set earlier than `"2026-03-01"` — the one config value with a hard-coded floor check, enforcing goal #3's "never loosened" | `is_candidate()` predicate |
| `sample_seed` | int | any int | `stratified_sample_sequence` RNG seed |
| `probe_batch_size` | int | ≥ 1 | Records probed before re-checking the survivor/sweep stop conditions |
| `target_set_size` | int | 1–200; `load_settings()` raises if > 200 (goal #11's ceiling, enforced) | Survivor stop condition |
| `probe_max_records` | int | ≥ 1 | Sweep stop condition |
| `scenario_trial_size` | int | ≥ 1 | §7 trial size per scenario (may yield fewer if a scenario's eligible pool is smaller) |
| `price_input_per_million_usd` / `price_output_per_million_usd` | float | `>= PINNED_PRICE_INPUT_USD_PER_MILLION` / `>= PINNED_PRICE_OUTPUT_USD_PER_MILLION` (5.00 / 30.00); `load_settings()` raises `ValueError` otherwise — the one override point if OpenAI's published rate INCREASES, never a way to shrink the effective ceiling by under-pricing | `SpendBudget`'s per-token rate (§3) |
| `total_spend_ceiling_usd` | float | > 0 | `SpendBudget`'s hard ceiling, checked via `reserve()` before every single API call across BOTH the scenario trial and curation (§3) — not just after a batch |
| `judge_confidence_floor` | float | `>= 0.7`; `load_settings()` raises `ValueError` otherwise (goal's near-miss guard, §4 — a floor, not a free parameter) | §4 near-miss guard |
| `dotenv_path` | str | use-time check; missing → logged warning | `load_env()` |
| `cleared_dir` / `scratch_dir` | str | parent created on write for scratch; `cleared_dir` must already exist (never auto-created — an accidental fresh directory silently "shipping" nothing is worse than a clear FileNotFoundError) | Output roots |

**Env vars:** `OPENAI_API_KEY` (prep's `.env`) — the only one. `CARVER_API_KEY`/any Carver
key: never read anywhere in `prep/` (the corpus is a local read-only file, not an API).

### `template/` config surface

No `config.yaml` — Mastra templates are TypeScript-config-native (goal #12's stack decision);
all "config" is `src/config.ts` (§8) plus `template/.env` (`OPENAI_API_KEY` only, read
implicitly by the model router). `firmProfile.ts`'s `DEMO_FIRM_PROFILE` is the one runtime
"parameter" a fork would edit — documented as such in the README.

---

## 14. Testing strategy

### `prep/` — pytest, stubbed client, no key/network (mirrors `gics-topic-tagging` exactly)

`tests/stubs.py` (importable, avoiding the `tests/` package self-import trap documented in
`docs/LESSONS.md`): `StubOpenAIClient` (configurable canned response per call index),
`RecordingStubClient` (captures `kwargs`, asserting no `temperature` param and correct
`reasoning_effort`/`max_completion_tokens`), `TruncatingStubClient` (`finish_reason=
"length"`).

| Test module | Representative cases |
|---|---|
| `test_reader.py` | streams a 3-line fixture without loading whole file (assert via a generator-exhaustion check, not a memory profiler); malformed line skipped + warned; missing file → `FileNotFoundError` |
| `test_extract.py` | every `FIELD_MAP` path resolves against the real sample record fixture; missing nested path → `None`, not `KeyError`; missing `id` → `extract_record` returns `None` |
| `test_candidates.py` | each predicate individually (cutoff-date boundary at exactly `2026-03-01` passes, `2026-02-28` fails; snapshot-date boundary at exactly `2026-07-11` passes, `2026-07-12` fails; **`test_snapshot_upper_bound_catches_rot_even_when_valid_flag_lies`** — a `2569-01-01`, `valid=True` fixture is rejected by the upper bound alone; each of the 8 actionable types passes, `"press release"` fails; `impact_label="medium"` fails; empty `key_requirements` fails; well-formed-but-unresolved URL still passes filter-time check); **`test_duplicate_ids_deduped`** — the sole test of `filter_candidates`'s dedup (first occurrence wins) |
| `test_urls.py` | `extract_urls` against the real `reg_rules` prose-with-parenthetical-URL sample; `resolve_url` against a stub transport (httpx `MockTransport`) covering 200/404/timeout/dns-error, and the HEAD-then-GET-retry path |
| `test_sampling.py` | determinism (same seed → identical sequence), proportionality, full-pool coverage (`len(sequence) == len(candidates)`) |
| `test_probe.py` | `build_task_instance` excludes every leaked-field substring across a fixture battery (rubric #11's assertion); Stage B structured response parses via `StubClient` |
| `test_judge.py` | `parse_and_validate_verdicts`: duplicate `obligation_id` in response → first wins; omitted id → `"uncertain"`, confidence `0.0`, `applies_to_draft=False`, `omission_material=False`, never `"violation"`; hallucinated/unrequested id in response → dropped, never surfaced; malformed JSON → retry once → all-omission fallback (including the applicability/materiality defaults) |
| `test_scoring.py` | one test per `CitationScore`/`DateScore`/`ObligationScore` outcome value (4 + 5 + 4 = 13 cases, `ObligationScore` now including `not_applicable`) against `scoring_golden.json`, explicitly asserting `is_failure` is `True` for exactly `citation_fabricated`/`date_wrong`/`violation-above-floor-with-both-flags-true` and `False` for every other outcome (including `citation_alternative_real`, `date_missing`/`date_uncertain_attribution`, and — the applicability fix, §4 — a `verdict="violation"` with `confidence>=floor` but `applies_to_draft=False` OR `omission_material=False`); `score_missed_obligation` returns `not_applicable`/`is_failure=False` without consulting `judge_result` at all when `is_eligible(record, scenario)` is `False`; `score_compliance_date` called with a non-`citation_correct` `CitationScore` always returns `date_uncertain_attribution` regardless of whether the raw dates would otherwise match; failure-bar OR-logic (each of the 3 dimensions alone is sufficient; all-non-failure is rejected); `SCORE_OUTCOME_TO_FAILURE_MODE`/`STAGE_OF_MODE` round-trip for exactly the 3 closed values (§5) |
| `test_scenario_decision.py` | `_tag_matches_keyword`: `"ai"` matches `"Generative AI"` but not `"retail"`/`"email"` (word-boundary regex); a US-jurisdiction AI-tagged fixture is `is_eligible(..., SCENARIO_A)` **False** (jurisdiction gate), an identical fixture with `country="DE"` is **True**; **`test_marketing_alone_not_eligible_for_b`** — a fixture tagged `["marketing"]` only (no financial term) is `is_eligible(..., SCENARIO_B)` **False**; an identical fixture additionally tagged `["consumer credit"]` is **True**; a fixture tagged only `["financial promotion"]` (a combined term) is **True** with no second tag needed; a fixture eligible for BOTH scenarios appears in both trials; `mean_strength` tie (`0.0-0.0`, empty trials) → `A`; `B` wins on strictly higher MEAN strength even with a smaller trial (proving normalization, not raw pool size, drives the outcome — the fairness fix); each scenario's actual `trial_size` may be `< scenario_trial_size` without error; evidence file shape |
| `test_schema.py` | `validate_cleared_record` rejects an `attestation` other than `"approved"`, rejects an unlisted extra key, rejects empty `baseline_failures`, rejects a `BaselineFailure.stage` that disagrees with `STAGE_OF_MODE[mode]`; **`test_no_unreviewed_records_in_cleared_dir`** (§6) |
| `test_curate.py` | all stop conditions individually (`BudgetExhausted` mid-batch, survivor-ceiling, sweep-cap, pool-exhausted) via a stub client returning canned failure/pass patterns; the three non-budget conditions are only checked at a batch boundary (never stops mid-batch), while a budget exhaustion can stop mid-batch; **`test_record_actual_cannot_leave_spend_above_ceiling`** (worst-case usage stays within ceiling with no exception; a simulated accounting anomaly raises `BudgetPoisoned` and permanently blocks further `reserve()` calls) (§3) |
| `test_run_prep.py` | `main()` filters `all_candidates` through `is_eligible(r, winning_scenario)` before ever constructing `run_curation`'s input list (§4's applicability fix) — a fixture pool containing both eligible and ineligible records asserts only the eligible ones reach the stub `run_curation` call |
| `test_config.py` | **`test_model_id_matches_template`** — the cross-language drift check (§8) reading `template/src/config.ts` as text; **`test_judge_confidence_floor_matches_template`** — the analogous drift check (§9c); `load_settings()` raises `ValueError` for `judge_confidence_floor: 0.5` (below the 0.7 floor) and for `price_input_per_million_usd`/`price_output_per_million_usd` below `PINNED_PRICE_*_USD_PER_MILLION`; `candidate_cutoff_date`/`target_set_size` boundary cases (already covered, §13); confirms `Settings` has NO `snapshot_date` field at all (an unknown-key `ValueError` if one is present in `config.yaml`, proving it cannot be reintroduced as a mutable key) |
| `test_review.py` | `record_signoff` has no parameter capable of overriding `title`/`why_it_matters`/any extracted field (a `TypeError` on an attempted extra kwarg, or simply: the function signature only accepts `record`/`reviewer`/`obligation_confirmations`); citation auto-selected with no prompt when exactly one URL resolves, prompted when more than one does; `ask_obligation_confirmations` returns `None` immediately for a fixture with no `missed_obligation` evidence (no questions asked); for a fixture WITH `missed_obligation` evidence, any single `False` answer among the three questions makes `review.py`'s CLI flow refuse to reach `approve` at all (routes to `record_rejection` instead); `validate_cleared_record` rejects a `human_review` with `obligation_applies_confirmed=True` but no `missed_obligation` evidence present (a stray/inconsistent confirmation) |
| `test_generate_template_config.py` | `test_trigger_tie_broken_by_id_ascending` (above); `emit_template_config` raises `ValueError` on an empty `winner_records`; the emitted `.ts` fragments (rendered via the fixed templates, §7) contain the trigger's real `id`/`FirmProfile` fields, never an empty string; step 5's narrowing-survives-generation assertion actually fires (raises) when given a deliberately non-matching firm profile fixture |

### `template/` — Vitest

| Test file | Cases | Network? |
|---|---|---|
| `schema.test.ts` | vendored `cleared-set.json` parses against `ClearedRecordSchema` for every record | No |
| `narrowObligations.test.ts` | zero-required-match (excluded even with high rank-score inputs); exactly-one-match; more-than-five-matches (ranking, not just the gate, is exercised); jurisdiction-only match with no industry/function overlap is excluded (required-AND semantics); `test_demo_trigger_record_survives_narrowing` | No |
| `carverGuardrail.test.ts` | agents share `instructions`/`model` (reference equality); a synthetic verdict fixture drives each of high/medium/low through enforcement (§9c, including the "medium"/"low" paths that real data never reaches — the Goal-issue-callout dead-code paths, exercised here only); **audit writes** — `new CarverGuardrail(fakeAuditWriter)` (a stub `AuditWriter` injected via the constructor, §9) asserts `fakeAuditWriter.write()` is called exactly once with the correct `severity`/`action` for each of high/medium/low, INCLUDING the high/abort path (asserted by catching the thrown tripwire and checking the stub was called before the throw); zero-violation case asserts no write at all | No (stubbed processor input, stubbed judge response) |
| `comparisonWorkflow.test.ts` | tripwire-containment proof, asserting the discriminated union's non-null `blocked_draft`/`reason`/`processorId`/`record.id` (matching `DEMO_TRIGGER_RECORD_ID` exactly) on a real live run (§10) | **Yes** |
| `scorers.test.ts` | golden-fixture parity (§12) | No |
| `evals.test.ts` | `runScoreboard()` prints a material gap; HTML report has no external refs; report generator rejects a non-blocked result; report escapes injected `<script>` content (§11); report renders both real branch outputs (`baseline.text` AND `guarded.blocked_draft`) plus the matching record's title/citation | **Yes** |

### Stress scenarios (task §14 / rubric §18) — specified behavior, cross-referenced

| Scenario | Where specified |
|---|---|
| Empty narrowing result | §9(a) — pass-through, no `auditWriter.write()` |
| Tripwire in `.parallel()` | §10 — dual-layer containment + live test |
| Unresolvable citation URL | §2 (filter-time well-formed only) + §4 (`citation_fabricated` outcome) + §6 (record dropped if *no* URL resolves) |
| Garbage/absent ground-truth compliance date | §4 `DateScore.not_applicable` |
| Malformed judge JSON | §4 — retry once, then `uncertain` (never `violation`) |
| Zero probe survivors | §3's stop conditions still terminate cleanly (probed cap or spend cap hits with `survivors=[]`); `run_prep.py` prints "0 records survived — see goal #11: ship nothing rather than pad" and exits 0 (not an error — an honest empty result) |
| Non-ASCII regulator names | `extract_record`/`to_json` use `ensure_ascii=False` throughout (mirrors `gics-topic-tagging` convention); a fixture record with a non-Latin regulator name round-trips in `test_schema.py` |
| Duplicate records | `filter_candidates` (§2) is the sole dedup layer — a local `seen: set[str]` keyed on `artifact_id`, first occurrence in file order wins; no other module deduplicates or assumes a second pass happened; `test_candidates.py::test_duplicate_ids_deduped` |
| A citation that dies between clearing and demo | Out of scope for automated re-checking in v1 (no scheduled re-validation job) — explicitly noted in the README as a known limitation: `data/cleared/` citations are validated at clearing time only; a stale link found later is a manual fix (edit + re-review), not an automated concern |

---

## 15. Error handling, determinism & cost guarantees

### Error handling (`prep/`)

| Failure point | Handling |
|---|---|
| `config.yaml` missing/invalid | `load_settings()` raises `FileNotFoundError`/`ValueError`; exits |
| `annotations_path` missing | `stream_annotations()` raises `FileNotFoundError` |
| Malformed JSONL line | Skipped + logged `WARNING`; stream continues |
| `.env` missing | `load_env()` logs `WARNING`; proceeds (key may be in shell env) |
| `OPENAI_API_KEY` absent | `make_client()` raises `KeyError` with a clear message |
| OpenAI API error (probe/judge) | One retry with exponential backoff (1s) — the retry itself reserves its own `SpendBudget` slot before firing (§3); if both attempts fail, the record is marked `probe_error` and **excluded from survivors** (never counted as a failure by omission — an API error is not evidence of a baseline failure) |
| `SpendBudget.reserve()` raises `BudgetExhausted` | `run_curation`/`decide_scenario` catch it and stop the run immediately with `stop_reason="spend_ceiling"` (§3) — never retried, never silently skipped to the next record |
| `resolve_url` network error | Treated as "does not resolve" (fail-closed, matching goal's "if it doesn't resolve, the record is out") |
| Judge malformed JSON | `parse_and_validate_verdicts` (§4): retry once; if still malformed, every requested obligation gets the omission fallback (`"uncertain"`), never `"violation"` |
| `data/cleared/` directory missing | `to_json()` / `run_prep.py --verify-cleared` raise `FileNotFoundError` — never auto-created (§13) |
| Attempted write of an unattested (or non-`"approved"`) record | `validate_cleared_record()` raises before any write occurs |

### Error handling (`template/`)

| Failure point | Handling |
|---|---|
| `OPENAI_API_KEY` absent | Mastra's model router raises with "which environment variable to set" (its own documented behavior) — no custom handling needed |
| Guarded-step tripwire (return or throw) | §10 dual-layer containment; workflow status stays `"success"` |
| `narrowObligations` given a firm profile matching zero records | §9(a) pass-through |
| Verdict-stage malformed structured output | Mastra's structured-output path itself retries per `maxProcessorRetries` (§8); if still malformed after retries, the processor treats it as no violation (fail-open on parse failure, since fail-closed here would mean spuriously blocking every draft on a transient API hiccup — a deliberate, stated choice, distinct from prep's fail-closed URL check where the risk is inverted) |
| Vendored `cleared-set.json` fails schema validation | `schema.test.ts` fails the build — never a runtime concern in the shipped template |

### Determinism guarantees

| Property | Guarantee |
|---|---|
| Stratified sampling | Same seed + same candidate list order → identical sequence (Hamilton allocation) |
| Candidate filtering / extraction | Pure functions over file order — deterministic given the same snapshot |
| Probe replay | Exact for any `(record, stage)` pair already logged under `--replay`; new pairs still call the live API (§3) |
| Cleared-set → template vendoring | A one-time, explicit copy step (`cp prep/data/cleared/cleared_records.json template/src/data/cleared-set.json`, documented in the README, not automated — keeping the "vendored" nature of the data an explicit, reviewable act, matching goal #1's "self-contained, vendored" framing) |
| Narrowing / enforcement | Pure, synchronous, no randomness |
| Scenario decision | Same seed + same trial pool + same `INDUSTRY_TAG_TO_BUCKET` table → identical eligibility, trial composition, and winner (§7) |

### Cost guarantees

`prep`'s spend is bounded by `SpendBudget` (§3): every API call, including retries and both
scenario-trial arms, reserves its own worst-case cost against `total_spend_ceiling_usd`
**before** firing — so cumulative actual spend can never exceed the ceiling, not merely
"usually stays under it." `npm test`'s spend is bounded by `data/cleared/`'s fixed size (≤200
records, ≤2 items each for the baseline pass, 1 for the guarded pass) — both halves' worst-case
spend is calculable from `config.yaml`/`config.ts` alone before running, and both are stated
in the README with the current pricing snapshot date.

---

## Pinned dependencies

### `prep/requirements.txt`

```
openai==1.76.0
httpx==0.28.1
PyYAML==6.0.2
python-dotenv==1.0.1
```

### `prep/requirements-dev.txt`

```
pytest==8.3.5
pytest-cov==5.0.0
```

### `template/package.json` dependencies — exact pins, no caret/range

```json
{
  "dependencies": { "@mastra/core": "1.51.0", "zod": "4.0.0" },
  "devDependencies": { "mastra": "1.51.0", "typescript": "5.7.3", "tsx": "4.19.2", "vitest": "2.1.8", "@types/node": "22.13.0" }
}
```

Exact versions, not `^`/`~` ranges — matching `prep/requirements.txt`'s `==` pinning
discipline on the TypeScript side (goal's general "pin dependencies" convention, applied
uniformly to both halves rather than only the Python one). `@mastra/core@1.51.0` and
`zod@4.0.0` are the versions verified current/compatible as of 2026-07-16 (`npm show
@mastra/core version`, `mastra.ai/blog/model-router`); `mastra`/`typescript`/`tsx`/`vitest`/
`@types/node` are floors verified compatible at spec time — confirm the exact resolved patch
via `npm install` and commit the resulting `package-lock.json` at implementation time (stage
02), updating these literals to match rather than leaving a range for `npm` to silently
re-resolve on a later install. No `@ai-sdk/openai` or any other AI SDK package (goal #9) —
the model router in `@mastra/core@1.51.0` resolves `"openai/gpt-5.6-sol"` from
`OPENAI_API_KEY` alone (verified 2026-07-16, `mastra.ai/blog/model-router`).

---

## `.gitignore` (project-local, `projects/mastra-guardrail/.gitignore`)

```
node_modules/
.mastra/
prep/.venv/
prep/data/scratch/
prep/.env
template/.env
template/output/
```

`prep/data/cleared/` and `template/src/data/cleared-set.json` are **not** listed — both are
tracked, per goal's explicit "the deliverable" framing.

---

## Out of scope (v1 — explicitly deferred)

- **RAG / vector store / embeddings** anywhere (goal #7) — the cleared set is small enough for
  in-memory array filtering.
- **Live Carver API** — `prep/` reads the static JSONL snapshot only; no Carver credential.
- **Mastra Platform** (`projects.mastra.ai`) — Studio (`mastra dev`, local/OSS) is used;
  the hosted product is never signed up for, never referenced in config.
- **Multi-agent orchestration** beyond the two agents in `compareWorkflow` — no planner,
  no sub-agent delegation.
- **Building both scenarios** — the loser's prompt templates remain in `scenarios.py` /
  `prompts.ts` as inert data (harmless to leave defined; never wired into an agent or workflow)
  but are not exercised beyond the §7 trial.
- **Automated re-validation of shipped citations** post-clearing (§14's last stress row).
- **Promotion to `carver-dags`** — out of scope; would follow the documented promotion path
  in `docs/development/conventions.md` if this ever becomes a production pipeline.
- **Streaming** output processors (`processOutputStream`) — only the non-streaming
  `processOutputResult` path is implemented; Studio's chat UI and `npm run demo` both use
  non-streaming `generate()`.
