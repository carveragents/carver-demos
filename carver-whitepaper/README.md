# Carver regulatory-dataset whitepaper

Self-contained interactive whitepaper plus the measured evidence behind it.

**Open `index.html` in a browser.** No build step, no server, no network — CSS and SVG are
inline, it renders in light and dark, and it prints.

---

## What is here

| path | what |
|---|---|
| `index.html` | the whitepaper (55 KB, fully self-contained) |
| `figures/whitepaper-data.json` | source of truth for every number rendered in §00–§07 |
| `figures/frontier-data.json` | source of truth for the cost–accuracy experiment |
| `figures/section1.json`, `section2.json` | mined corpus figures feeding `consolidate.py` |
| `scripts/mine_corpus.py` | scans the annotations snapshot → `section*.json` |
| `scripts/consolidate.py` | merges mined + measured figures → `whitepaper-data.json` |
| `experiments/EXPERIMENT-PLAN.md` | the pre-registered plan the experiment followed |
| `experiments/questions.json` | 26 questions + answer keys, committed *before* any arm ran |
| `experiments/QUESTION-SET-REVIEW.md` | the same set rendered for human review |
| `experiments/analysis.py` | `runs.jsonl` + `grades.jsonl` → `frontier-data.json` |
| `experiments/INTERNAL-DECK.md` | internal results deck |
| `experiments/spot-check-queue.md` | 112 judge verdicts awaiting human review |

**Single-source-of-truth rule:** every number rendered in `index.html` traces to a field in
`figures/*.json`. Do not hand-edit a figure into the HTML — put it in the JSON and reference it,
or the document and its evidence drift apart.

---

## What is NOT here, and why

The raw run-level datasets stay on the experiment branch, deliberately — they are working data,
not publishable artifacts:

| file | size | where |
|---|---|---|
| `runs.jsonl` | 1.4 MB | branch `flux/docs-carver-whitepaper` |
| `grades.jsonl` | 700 KB | branch `flux/docs-carver-whitepaper` |
| `grades-v1-clockconfound.jsonl` | 700 KB | branch `flux/docs-carver-whitepaper` |
| domain + full-corpus vector indices | ~10 GB | gitignored build artifacts, never committed |

**Consequence:** `experiments/analysis.py` cannot be re-run from this directory alone — it needs
`runs.jsonl` and `grades.jsonl` from the branch. `frontier-data.json` here is the committed output
of that run. If you need to reproduce or re-analyse, work on the branch.

The ~10 GB of vector indices are rebuildable from the corpus snapshot via
`mastra-studio-demo/scripts/build-domain-index.mjs`. The full-corpus index takes about 3 hours,
most of it the ANN build.

---

## The experiment in one paragraph

370 agent runs, four arms (memory-only · live web search · Carver over all 229,287 indexed
records · Carver over a curated per-sector slice), same model and prompts throughout so retrieval
is the only variable. 26 operator scenarios, answer keys pre-registered and committed before any
arm ran. Scored 6–8 checks per question, including two must-pass precision checks that cap a
question at zero — so a confident hallucination cannot score well. Grading was done by an
arm-blinded LLM judge. Headline: live web search is Pareto-dominated on this set, and grounding
buys essentially nothing on questions the model already knows — all of its value is on questions
where the model is blind.

Full caveats are on the "What this doesn't prove" slide of `INTERNAL-DECK.md`. The most important
one: the questions were sourced from the Carver corpus, so the Carver arms are advantaged by
construction.

---

## Honesty guards

`BUILD-NOTES.md` carries the standing list of claims this document is not allowed to make
(no speed claim, web cost is a floor not a ceiling, no Carver licence fee is modelled, projected
figures must be labelled projected). Read it before editing `index.html`.
