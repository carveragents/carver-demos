# Carver × Mastra — a compliance guardrail as a Mastra `outputProcessor`

An ordinary business agent with zero regulatory awareness, wrapped in a Mastra
`outputProcessor` that checks its drafts against real 2026 regulatory obligations and
blocks the ones that would violate one.

**The demo is a controlled experiment.** Two agents. The same model, the same
instructions, the same generation settings, the same task. Exactly one difference:

```ts
// src/agents/baselineAgent.ts
export const baselineAgent = new Agent({
  ...SHARED_AGENT_CONFIG,   // instructions + model + defaultOptions, from ONE object
  // NO tools, NO outputProcessors — the whole point of this arm.
});

// src/agents/guardedAgent.ts
export const guardedAgent = new Agent({
  ...SHARED_AGENT_CONFIG,                      // the SAME object baselineAgent spreads
  outputProcessors: [new CarverGuardrail()],   // THE ONLY DIFFERENCE between the two arms
});
```

Both arms spread the **same `SHARED_AGENT_CONFIG` object** — not two equal literals, the
same object, so they cannot drift apart. The baseline drafts freely and whatever it
produces is delivered. The guarded agent drafts the same thing, and its draft is checked
against the obligations Carver's data says apply to this firm before a word reaches the
caller.

That is the whole claim: **not a better model, not a bigger prompt — the same agent, with
regulatory data underneath it.**

> **Read this before you judge the data.** The mechanism described here is built and
> tested, but the dataset vendored in this template is **currently a synthetic development
> fixture — not real Carver records, with invented citations**. The real cleared set
> replaces one JSON file. See [Status](#status--what-is-built-and-what-is-not) for exactly
> what is and is not real yet.

---

## Quickstart

Node ≥ 22.13.0.

```bash
npm install
cp .env.example .env     # add your OPENAI_API_KEY
npm run dev              # Mastra Studio, http://localhost:4111
```

`OPENAI_API_KEY` is the only secret this project reads.

**Studio needs no account.** `npm run dev` runs `mastra dev`, the local, open-source dev
UI, served from your own machine. No Mastra account, no Mastra API key, no paid plan, no
sign-up. Mastra's paid hosted Platform is out of scope here and no token for it is ever
set. The OpenAI key is for the model calls the two agents make — nothing else here is
hosted or billed.

| Command | What it does |
|---|---|
| `npm run dev` | Mastra Studio on `:4111` — the mechanism, as a live graph |
| `npm run demo` | Runs the real workflow, writes `output/demo-report.html` |
| `npm run demo:prompt` | Prints the demo's prompt to stdout, for pasting into Studio |
| `npm test` | Typecheck + the full test suite |
| `npm run typecheck` | `tsc --noEmit` |

---

## ⚠️ The guardrail working looks like a crash. Read this before you run it.

Mastra runs output processors **inside a workflow**. So when the guardrail does its job
and calls `abort()`, Mastra reports its own internal abort the way it reports any failing
step: **a red `[WORKFLOW] Error executing step …` and a stack trace on stderr.**

**That red text is the success path.** It is what a block looks like. Nothing is broken,
and you have not misconfigured anything.

This template cannot silence Mastra's stderr and does not try. What it does instead is
make sure the thing you read as "the answer" says BLOCK:

- **The workflow run itself succeeds.** `run.start()` resolves `status: "success"`, never
  `"tripwire"` — the tripwire is contained inside the guarded step and never propagates
  out of it. This is also what keeps the baseline branch beside it running to completion:
  a block on one arm must never kill the other, or there is no comparison.
- **`outcome` is the first key of the workflow's output** — a top-level
  `"BLOCKED" | "DELIVERED"` enum, derived from the result it summarises and cross-checked
  by a schema refinement so it cannot disagree with it. It is the first thing Studio's
  result panel renders.
- **`npm run demo` warns before the run and restates the verdict as the last thing
  printed**, after the stack trace, with exit code `0` for a block.
- **The HTML report leads with the verdict stamp** and names the stack trace on the page.

---

## The three surfaces

### 1. Studio — the mechanism

`npm run dev` → `http://localhost:4111`.

Studio auto-discovers whatever is registered on the `Mastra` instance; there is no
Studio-specific code in this template. You will see **three workflows**, and only the
first is the demo:

| Workflow | What it is |
|---|---|
| **`compareWorkflow`** | **THE DEMO** — baseline and guarded, in parallel, then a report step |
| `deliveryWorkflow` | An eval target for `npm test`. Not the demo. |
| `stageBWorkflow` | An eval target for `npm test`. Not the demo. |

The two eval targets are registered because they must be — their steps resolve agents via
`mastra.getAgent(...)`, and Mastra supplies that instance *through* registration, so
unregistered they would throw and `npm test` could not run. The cost is a Studio list with
three entries where the demo has one; each workflow's own `description` says which it is,
where Studio shows it.

**To run the demo in Studio:**

1. Open `compareWorkflow`.
2. Get the prompt: `npm run demo:prompt` prints it to stdout. Paste it into the run form's
   `prompt` field. (It is generated from the vendored data and the scenario templates, not
   hand-typed here, so the Studio path and `npm run demo` ask the identical question.)
3. `compareWorkflow` declares a `requestContextSchema`, so Studio renders a form for
   `firmProfile` — the firm the obligations are narrowed against. Supply it there.
4. Run. One branch completes; the other tripwires. The traces show the processor firing
   and which Carver record matched.

The firm profile travels as **request context, never as prompt text** — it must reach the
guardrail without entering either agent's prompt, or the two arms would differ in their
input rather than only in whether Carver data gates their output.

### 2. `npm run demo` — the contrast

Runs the same `compareWorkflow` against the real model and writes
`output/demo-report.html` **from that run's own output** — never hand-authored. It is a
self-contained file: inline CSS, no external assets, no scripts, no fonts, no server. It
opens over `file://` with the network off, so it can be read by someone who never runs
this.

The report puts the two drafts side by side, then the Carver obligation that fired, its
clickable citation and its compliance date. Its **controlled-experiment table** is where
you verify the "same config" claim in about four seconds: every shared knob — model,
reasoning effort, max output tokens, instructions, task prompt — printed for both arms,
with the single differing row (Carver data) marked. Stating "same model, same config" in
prose asks you to take our word for it; the table lets you check.

Exit codes: `0` blocked and the report was written · `1` infrastructure broke · `2` the run
worked and the guardrail declined to block (an expected minority outcome, not a crash — no
report is written, because a report is only ever generated from a run that really blocked).

### 3. `npm test` — the scoreboard

The suite is free and needs **no API key**: it stubs the language model. That is not a
lesser set — it exercises the *real* scorers, the real `runScoreboard`, the real `runEvals`
and the real workflows through a real Mastra, with only the model itself stubbed.

`runScoreboard()` builds a paired baseline-vs-guarded table via `runEvals`, rendered by
`printScoreboard`:

| Metric | Population | Arms compared |
|---|---|---|
| Shipped a violating draft *(lower=better)* | scored | baseline vs guarded |
| Blocked the draft *(higher=better)* | scored | baseline vs guarded |
| Caught the known obligation *(higher=better)* | scored | guarded |
| Benign-task pass rate *(higher=better)* | negative control | guarded |
| Shipped a violating draft *(lower=better)* | crowdedOut | baseline |
| Gave a wrong compliance date *(lower=better)* | stageB | baseline |

The **negative control** matters as much as the rest: a guardrail that blocks everything
would ace every other row. `test_blanket_guardrail_fails_the_suite` proves the suite
detects exactly that degenerate system, and it is deliberately free — proving the harness
can catch a fake must not itself cost money.

**What `npm test` does not do yet — say it before you run it and wonder.** The table above
is what `printScoreboard` renders, and the harness that fills it is real and tested. But
the **live measurement against the real model, and the thresholds it has to clear, are not
yet wired into the suite**. Every case that runs today runs against a stub. So `npm test`
green means "the harness and the scorers are correct", **not** "the gap has been measured".
That measurement needs the billed run, and it is the last step.

---

## Status — what is built, and what is not

**The mechanism is built, tested and green. Two things are not yet real**, and they are
stated here rather than left to be discovered: a reader who clicked a citation and found
nothing would reasonably conclude we invent records, which is the one charge this project
cannot afford.

- **`src/data/cleared-set.json` currently holds a synthetic, schema-conforming development
  fixture** (6 records, ids `art-100x`). It is not real Carver data, its citations are
  invented for the fixture rather than resolved from a regulator, and you should not
  expect its links to lead anywhere. It exists so every module can be built and proven
  before the curation run is paid for.
- **The real cleared set replaces that one file at vendoring.** Nothing else moves:
  `tests/schema.test.ts` Zod-parses whatever is in that path, which is the mechanism that
  makes the swap safe rather than hopeful.
- **The live scoreboard bars are not yet wired into `npm test`.** The scorers,
  `runScoreboard`, `runEvals` and the workflows are all real and all exercised by the
  suite — against a stubbed model. The thresholds that need real model calls land with the
  real run.

Everything else this README describes is built and tested today.

---

## The baseline model, and why it is the strongest one

| | |
|---|---|
| **Baseline model** | `openai/gpt-5.6-sol` |
| **Its knowledge cutoff** | `2026-02-16` |
| **Carver snapshot** | `2026-07-11` |

Both arms run this model. It is pinned once, in `src/config.ts`, and imported by both — no
second literal anywhere.

**It is deliberately OpenAI's current flagship — the strongest baseline available, not an
old one chosen to make the gap look bigger.** The temptation is real: an earlier cutoff
means a wider blind spot and more failures to harvest. That is rigging, and it is the one
objection that would kill this artifact — *"you benchmarked against an old model"* — because
the claim here is about Carver, not about model age. So the strongest opponent is the point:
a gap that survives the newest flagship is a gap about the **data**, and cannot be waved
away as an artifact of a weak baseline. The 31% smaller candidate pool that this costs is
the deliberate price.

The delta is not "the model is bad". It is **structural**. The cleared set is selected to
contain only obligations published after `2026-02-16` — with a deliberate margin, so a
document the model might have seen cannot slip in — which means they are not in its weights
to recall at all. No prompt fixes that; there is nothing there to prompt for.

That date rule is enforced **in the Python prep pipeline, where the set is curated**. It is
worth being precise about what the template can and cannot show you: a shipped record
carries the model id and cutoff it was probed against (`src/schema.ts` pins both to
literals), but it carries **no publication-date field**, so nothing here re-derives the
filter. If you want to audit that rule rather than take it on trust, it lives in prep, not
in this package.

`README.test.ts` reads those three values out of `src/config.ts` **as text** and asserts
this README states them. The disclosure is a test failure when it drifts, not a
documentation aspiration.

### Swapping providers

Mastra's model router makes the provider a string, so the model is a **config constant, not
a hard dependency**. Change one line:

```ts
// src/config.ts
export const MODEL_ID = "openai/gpt-5.6-sol";
```

Use the `provider/model` form. Note that `MODEL_ID` is pinned to an **explicit model id,
never an alias** — an alias's target changes, and pinning a knowledge cutoff to a moving
target is a time bomb that passes every check the day it re-points.

**If you swap the model, `MODEL_CUTOFF` must be re-derived** from the new model's
documented cutoff, and the candidate filter re-derived from that. Tighten it if the new
cutoff is later; never loosen it to grow the dataset. The two constants are not
independent: a model swap that leaves the old cutoff in place silently corrupts the
experiment while every test still passes.

We build and verify on OpenAI because that is the key we have. The comparison itself is
provider-agnostic — what would be fatal is a *mismatch*, probing with one model and demoing
with another, which would silently measure a model comparison and report it as Carver's
contribution.

---

## How the guardrail works

`CarverGuardrail` (`src/processors/carverGuardrail.ts`) is a Mastra `outputProcessor` with
three stages:

**(a) Deterministic narrowing** — `narrowObligationsPure` filters the cleared set by firm
profile (jurisdiction, industry, impacted functions) down to **≤ 5** candidate
obligations. No LLM, fast, explainable. It ranks against the pinned `SNAPSHOT_DATE`, never
`Date.now()`, so narrowing is deterministic on every machine and every run.

**(b) LLM verdict** — the same pinned model judges the draft against *only* those
candidates and returns a Zod-typed structured verdict. A verdict counts only if its
confidence clears `JUDGE_CONFIDENCE_FLOOR` (`0.7`) — a floor against near-misses, not a
tunable.

**(c) Enforcement** — the severity ladder, driven by **Carver's own `impact_label`**, never
by a hand-invented rule:

| `impact_label` | Action |
|---|---|
| `high` | audit + `abort()` — the hard tripwire |
| `medium` | audit + annotate the draft with a warning |
| `low` | audit + pass |

That the *data* sets the threshold is the argument that Carver does work a prompt cannot.

**Severity-ladder coverage, plainly:** every record in the cleared set is
`impact_label: "high"` **by construction** — the candidate filter admits nothing else, and
the schema pins the field to the literal `"high"`. So against real data only the `high`
branch is ever reached. The `medium` and `low` branches are real code, but they are
**exercised only by unit tests**, which drive them through an injected cleared set. Read
the ladder as "one live branch and two tested-but-dormant ones", not as three paths this
demo takes.

### What the guardrail records

Every enforcement decision is appended to `.mastra/output/guardrail-audit.jsonl` — the
obligations judged violated, the severity Carver's data assigned, and the action taken. A
passing draft writes nothing; the log's semantics are "a violation occurred".

This makes a run **auditable**: every enforcement decision is on disk and can be read after
the fact. That is the claim, and it is the whole of it. There is **no replay harness** — a
past run cannot be re-executed from its log, and these are live model calls, so a second
run is a second sample rather than the same one returned again.

---

## The dataset

`src/data/cleared-set.json` is vendored — the template is self-contained and reads no
network, no Carver API and no database. There is no RAG, no vector store and no
embeddings: a small set of records is a JSON file plus a deterministic filter.

Each record is a **Carver annotation** — the structured compliance object Carver's agents
build from one raw regulatory feed entry. Where the raw entry was title + link + date, the
annotation carries `key_requirements`, `compliance_date`, the `citation` and its URL,
`impacted_business`, `impacted_functions`, the regulator, the jurisdiction, and Carver's own
`impact_label`. That annotation layer is the thing a prompt cannot substitute for.

**The selection rule** (enforced in the Python prep pipeline, not here) is what makes the
set worth anything:

- Published after the baseline's knowledge cutoff, with a margin — so pretraining
  structurally cannot compete.
- Actionable `update_type`, `impact_label == "high"`, non-empty `key_requirements`.
- **A record enters only with recorded evidence of how the baseline actually failed it.**
  Every record carries `baseline_failures[]` — the mode (`missed_obligation`, `date_wrong`,
  `citation_fabricated`), the stage, an excerpt of what the baseline really said, and the
  judge's rationale. Records the baseline handles competently are *excluded*: a big set
  padded with them would destroy the only claim this template exists to make.
- **Every record is human-reviewed.** `human_review` carries the reviewer, the timestamp
  and an `approved` attestation, and the schema pins that literal. There is no
  batch-approve path.
- Every citation URL resolved at clearing time.

The schema (`src/schema.ts`) enforces what it can: `impact_label` is the literal `"high"`,
`baseline_failures` is `.min(1)`, `human_review.attestation` is the literal `"approved"`,
`citation.url` must be a URL, and `model_id`/`model_cutoff`/`snapshot_date` are pinned
literals. A record that drifts fails `tests/schema.test.ts`.

---

## What this measures — and what it does not

The honest scope, because an accurate narrow claim beats an impressive broad one a careful
reader can falsify:

- **The runtime scoreboard does not detect fabricated citations.** It has no URL resolver —
  resolving live URLs mid-demo would mean network calls inside the demo and a new failure
  mode on stage. Its citation-adjacent row measures **wrong compliance dates only**, and is
  labelled as exactly that. Citation fabrication *is* detected — in the Python prep
  pipeline, at curation time, where the resolver lives; that is where a record's
  `citation_fabricated` evidence comes from. The template simply does not re-derive it.
- **The citation the report displays is Carver's own ground truth**, rendered so you can
  click it. It is not a claim about anything the baseline cited.
- **One run is an anecdote**, and the demo report is one run. The scoreboard is where the
  measurable version of the question lives — across the whole cleared set, not one record.
  See [Status](#status--what-is-built-and-what-is-not) for how much of it is wired today.
- **The baseline's draft is never judged.** Nothing was there to judge it — that is the
  point of the arm, not an oversight.

## Known limitations

- **Citations are validated at clearing time only.** There is no scheduled re-validation
  job. A link that dies afterwards is a manual fix — edit and re-review — not something
  this template detects.
- **`medium`/`low` enforcement is unit-test-only** against real data (see the severity
  ladder above).
- **Studio lists three workflows**, two of which are eval targets rather than the demo.
- **No replay harness** — a run's decisions can be read afterwards, but a past run cannot
  be re-executed from its log.
- The demo is scenario-locked: the persona, firm profile and trigger record are generated
  from the curation run's own decision, not hand-authored.

---

## Layout

```
src/
  config.ts               the pinned constants — model, cutoff, snapshot, floors
  schema.ts               ClearedRecord + the Zod contract the vendored data must meet
  firmProfile.ts          the firm the obligations are narrowed against
  mastra.ts               the Mastra instance — what `mastra dev` discovers
  agents/                 baseline, guarded, judge — baseline and guarded share ONE config
  processors/
    carverGuardrail.ts    THE PROCESSOR — narrow → judge → enforce
    tripwireContainment.ts  keeps a tripwire from killing the run or the other arm
  tools/narrowObligations.ts   stage (a): deterministic, ≤5, no LLM
  judge/                  stage (b): the structured verdict contract
  workflows/compareWorkflow.ts  THE DEMO — parallel arms, then a report step
  evals/                  the scoreboard: scorers + eval workflows
  report/                 the self-contained HTML report
  data/cleared-set.json   the vendored Carver records
  scenario/prompts.ts     generated — the scenario's prompts
scripts/
  demo.ts                 `npm run demo`
  printPrompt.ts          `npm run demo:prompt`
tests/                    vitest — no API key required
```

The template is self-contained and standalone: it imports nothing from the Python prep
pipeline or any sibling repository, and it runs from a fresh clone with only
`OPENAI_API_KEY`. Some modules carry doc comments naming the Python function their port
must stay in lockstep with — those are documentation of a dependency that deliberately does
not exist, not the dependency itself.
