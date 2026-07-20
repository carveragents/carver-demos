# prep/tools — corpus reconnaissance

Read-only analysis over the annotations corpus. Nothing here writes to
`data/cleared/`, mutates the pipeline, or is imported by it — these tools *use*
`mastra_prep` to answer questions about the data before you spend money.

Run everything from `prep/` (goal #13 fixes the CWD there):

```bash
cd mastra-guardrail/prep
PYTHONPATH=. .venv/bin/python tools/<tool>.py …
```

| Tool | Cost | Answers |
|---|---|---|
| `scan_yield.py` | free | How many candidates exist, and what do the scorers have to work with? |
| `mine_domains.py` | free | Which domain gives the strongest contrast? |
| `probe_targeted.py` | ~$0.03/rec | Does the baseline provably fail on a pool I choose? |
| `probe_recency.py` | ~$0.01/rec | Does the baseline even KNOW this post-cutoff event happened? |

## What these found (2026-07-20, snapshot 2026-07-06)

**The pool is there.** 7,036 candidates of 244,545 records across 1,189 distinct
regulators. `goal.md`'s 8,260 was the 2026-07-11 snapshot; the gap is almost
entirely July (136 vs 373). A 35:1 selection ratio against a 200-record target.

**The scenario predicates barely match this corpus.** Shipped
`scenarios.is_eligible` admits **28** records for scenario A and **1** for
scenario B — both far below `scenario_trial_min`. The data is not missing: 100%
of candidates carry both `impacted_business.industry` and `impacted_functions`.
The keyword sets simply do not match the corpus vocabulary. The corpus's dominant
financial value is `banking` (1,829 records), which is not in
`SCENARIO_B_FINANCIAL_TERMS` at all; `marketing` appears as an `impacted_function`
in only 113 of 7,036. And the predicate searches only those two coarse taxonomy
fields — never the title/summary/`key_requirements` text where the topical signal
actually lives. Widening to the text surface takes scenario B from 48 to 789.

**The probe found zero survivors — and the reason is not model strength.**
100 financial records, $2.26, zero. The outcome distribution is the finding:

| Scorer | Result across 83 probed |
|---|---|
| obligation | **83 `not_applicable`, `applies_to_draft: False` for all 83** |
| citation | 82 `citation_missing`, 1 `citation_alternative_real`, **0 fabricated** |
| date | 73 `not_applicable`, 10 `date_missing`, **0 wrong** |

`applies_to_draft: False` at 83/83 is a property of the *task*, not the model.
Scenario B asks for a generic promotional email built from coarse, non-leaking
fields; the record is a specific decision from a specific regulator. They never
intersect. The other two modes then cannot fire either: a model that declines to
cite (82/83) can never *fabricate* a citation, and 85.8% of candidates have no
ground-truth compliance date to be wrong about.

There is a real tension in the design here: the fair-test rule says don't leak the
record into the task, but the missed-obligation check needs the obligation to bear
on the draft. A task generic enough to satisfy the first cannot satisfy the second.
**Fix the task-record coupling before funding a full Phase 7 sweep.**

**Where the contrast actually lives.** `mine_domains.py` ranks domains on
regulator obscurity, tail length, and obligation depth:

| Domain | n | Regulators | Non-famous |
|---|---|---|---|
| cybersecurity | 103 | 40 | **100%** |
| insurance | 420 | 157 | 97% |
| energy | 226 | 106 | 88% |
| medical device | 294 | 65 | 93% |
| investment | 252 | 97 | 82% |
| financial services | 136 | 45 | **54%** |

Financial services is the *worst* domain in the corpus for this purpose — over
half its records come from bodies a frontier model knows cold. Cybersecurity is
the best, and its artifacts are maximally specific and unbluffable: *"Multiples
vulnérabilités dans les produits Schneider Electric"*, *"INC Ransom and Affiliate
Network operating in Australia"*.

That score is a **heuristic, not a measurement**. It predicts where the baseline
should be weak. `probe_recency.py` is what confirms it.

## The contrast that works — measured, cybersecurity, $0.35

20 cybersecurity records through `probe_recency.py`. Unlike the drafting probe,
this one produces a stark, reproducible gap. Three patterns, all demo-usable:

**Confident and stale (~9/20).** The baseline names the *exact real title* and
attaches an older date:

| Ground truth | Baseline said |
|---|---|
| ANSSI *Multiples vulnérabilités dans les VPN Check Point*, 2026-06-09 | same title, **18 June 2025** |
| ANSSI *…Stormshield Management Center*, 2026-06-29 | same title, **18 July 2025** |
| NCSC-NL *Ernstige kwetsbaarheden in Check Point…*, 2026-06-09 | same title, **18 december 2025** |
| CNIL data-security guidance, 2026-06-19 | *Guide… édition 2024*, **26 March 2024** |

**Honest wall (4/20).** NCSC-2026-0179, NCSC-2026-0180, CCN-CERT FortiBleed,
Hudson Rock — *"I'm not aware of…"*. Keep these: a demo claiming the baseline
always fails is disprovable in one question.

**Fabrication (≥1/20), the sharpest beat.** Asked about Canadian Centre alert
**AL26-014** (truly 2026-06-18), the baseline answered *"dated **July 17, 2026**"* —
an invented, fake-precise date later than both its own cutoff and the corpus
snapshot. Asked about **AL26-015** (2026-07-02) it went further and *corrected the
user*: "The identifier appears to be **AL25-015**, not 'AL26 015.'" Confidently
telling the user they are wrong about a real advisory is the most damning
behaviour in the whole sweep.

### Trap: empty answers are a bug, not a finding

The first run of this tool returned an empty string for all 20 records, which
reads exactly like "the model knows nothing". It was `max_completion_tokens=400`
at `reasoning_effort="medium"` — **reasoning tokens count against that budget on
the GPT-5 family**, so reasoning consumed the whole allowance and left nothing for
the message. Now 2000 / `low`. If you see blank answers, check this first before
concluding anything about the model.
