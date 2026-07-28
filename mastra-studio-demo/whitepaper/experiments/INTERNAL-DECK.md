# Carver vs web search vs memory
### What 370 measured agent runs say about cost, accuracy, and where grounding actually pays

Internal — for feedback, not external use
2026-07-28 · all numbers from `whitepaper/figures/frontier-data.json`

---

## Why we ran this

The whitepaper's §3 had a **seam**: dollar figures came from one benchmark, accuracy percentages
from a different one. You could not draw a cost-vs-accuracy point for any arm without mixing sources.

It also had a **credibility problem**: the memory-only baseline looked dramatically cheap
(~$12.70/1k) with no accuracy number next to it. A prospect reads that and asks the obvious
question — "so why would I pay for anything?"

**Goal:** one experiment where cost AND accuracy for every arm come from the *same runs*.

---

## What we tested — 4 arms

Same model (`gpt-5.6-sol`), same step cap, byte-identical prompts.
**Retrieval is the only variable.**

| arm | what it can reach |
|---|---|
| `baseline` | nothing — model memory only |
| `web` | live hosted web search |
| `carver-full` | **all 229,287** indexed corpus records |
| `carver-domain` | the curated per-sector slice (1.5k–7k records) our demos used |

The last two are the interesting pair: they separate **"Carver's data"** from
**"Carver's data that a human already narrowed to the right sector."**
Only the first is a capability a customer actually gets.

---

## A correction worth knowing about

Before this experiment, our Carver demos searched **~19,700 records — about 8% of the corpus** —
and each index was pre-aimed at its scenario's subject matter.

Scale forced a new access path. Measured:

| rows | brute-force query |
|---|---|
| 1,487 | 573 ms |
| 7,146 | 2,622 ms |
| 229,287 (projected) | **~90 s** ❌ |

Fix: compressed ANN index — **36.7 KB/vector** (vs 320 KB default), **137–266 ms** queries at full
scale. Build took 169 min, one-time.

**We can now demo against the whole dataset.** We could not before.

---

## The questions — 26, pre-registered

Each is a realistic operator situation. The system message describes the company;
the user message asks a naive planning question that **names no rule, deadline, or regulator**.
The obligation has to be *noticed*, not recalled from the prompt.

Sourced from the corpus, with answer keys written **before any arm ran** and committed to git —
the commit timestamp is the pre-registration proof.

**Example (q12):** a French crypto firm that already holds a MiCA authorisation asks
*"anything outstanding on the regulatory side, or are we fine?"*
Correct answer: MiCA is **not** sufficient — e-money-token services need PSD2 payment-institution
authorisation, due 2 March 2026.

---

## How we scored it

**6–8 checks per question** (avg 7.6), mixed regex and LLM judge.

Every question carries **two must-pass checks**:
- `cite-real` — cited instrument exists and governs this situation
- `no-fabricated-obligation` — asserts no duty that doesn't apply

**Failing either caps the question at 0.**

This matters: our old rubric was 5 regexes measuring *recall only*, so a confidently
hallucinating arm could have scored 100%. Errors are counted separately as
`miss` / `hallucination` / `stale` and never blended.

Judge is **arm-blinded** — it sees the scenario, the key, and the answer text. Not the arm name,
not the tool trace.

---

## Headline: the cost–accuracy frontier

| arm | accuracy | $/question | $/1k | median latency | p90 latency |
|---|---|---|---|---|---|
| baseline | 56% | $0.048 | $48 | 36.5s | 68.2s |
| web | 79% | $0.369 | $369 | 63.6s | **117.9s** |
| carver-full | **82%** | $0.203 | $203 | 38.1s | 51.6s |
| carver-domain | 81% | **$0.129** | **$129** | 36.6s | 54.6s |

### Web search is Pareto-dominated — on cost.

**carver-domain is 2.9× cheaper at indistinguishable accuracy** (81% vs 79%). carver-full is
1.8× cheaper. Web is also the slowest — p90 117.9s vs ~52s.

⚠️ **Do not claim Carver is "more accurate" than web from this.** The three retrieval arms are
separated by 1–3pp, and with 26 questions one question moves a mean by ~4pp — that gap is inside
the noise (see Appendix B). What is robust here is **cost and latency**, not the accuracy ranking.

Both axes from the same 312 runs. No seam.

---

## The finding I'd actually lead with

| stratum | n | baseline | web | carver-full | carver-domain |
|---|---|---|---|---|---|
| model already knows | 16 q | 79% | 84% | 79% | 79% |
| **model is blind** | 10 q | **27%** | 60% | 76% | **85%** |
| **silent-trigger tail** | 5 q | 22% | 86% | **100%** | 80% |

**Where the model already knows the answer, grounding buys nothing** — every arm ties at 79–84%.

All the value sits in the bottom two rows. That's a sharper and more sellable claim than
"Carver is more accurate": it tells a buyer *which questions* justify the spend.

---

## Breakeven

Cost per flawed answer avoided, vs the memory-only baseline:

| arm | extra $/question | accuracy gain | **$ per flawed answer avoided** |
|---|---|---|---|
| carver-domain | +$0.081 | +25pp | **$0.33** |
| carver-full | +$0.155 | +26pp | **$0.59** |
| web | +$0.321 | +23pp | $1.39 |

Baseline's flawed-answer rate is **100%** — every baseline run failed at least one check,
usually `provenance`: it produced **zero citations in 100% of answers**. Structural, not incidental.

---

## Three results that cut against us

**1. Full corpus does not beat curation.**
carver-full 82% vs carver-domain 81% — indistinguishable — for **1.6× the cost**. It earns its keep
in exactly one place: the silent-trigger tail, **100% vs 80%**. Honest claim: full-corpus reach buys
*tail coverage*, not general accuracy.

**1b. The three retrieval arms don't separate on overall accuracy at all.**
79% / 82% / 81% is one question's worth of noise. On this set we can defend *cost*, *latency*, and
the *stratum* gaps — not an accuracy ranking between web and Carver. Fixing that needs more
questions, not more runs.

**2. Baseline sits on the Pareto frontier.**
At $0.048 / 56%, nothing dominates it. For questions the model already knows, the cheap arm is
defensible. We should say so.

**3. The §06 replay projection is dead.**
We projected **$22.57/1k** assuming ~90% cache hits. Measured cache share: **51%** and **34%**.
carver-full fell 13%; carver-domain *rose* 10%. Measured: **$178** and **$136**/1k.
**Recommend deleting that box, not updating it.**
(What survives: web shows **0%** cached input and −8% — "web cost doesn't decline on repetition" holds.)

---

## A methodology bug we caught — and why it matters

First grading pass scored web at **44%**. Corrected, it scores **79%**.

Cause: our scenarios set a fictional "today" in mid-2026. Live web search legitimately returns
documents published *after* that date, and the judge failed those real citations as
"impossible as presented."

It hit **web only** — 19 of its 101 failed checks, **0 for every other arm**, because the Carver
indices are date-capped.

We re-graded **all 312 runs** under one corrected rubric rather than patching web alone.
The flawed pass is retained as `grades-v1-clockconfound.jsonl` so the correction is auditable.

**If we had shipped the first pass, we'd have published a 35-point error in our own favour.**

---

## What this doesn't prove

- **Questions are corpus-sourced**, so Carver arms are advantaged by construction. Mitigated
  (every obligation is public and web-reachable; baseline-knowable stratum is a fair control)
  but not eliminated.
- **26 questions, 4 domains.** Not a broad benchmark — and small enough that one question moves a
  pooled mean by ~4pp, which is wider than the gap between the three retrieval arms.
- **Our designed pre/post-cutoff split failed** — a 2026 record date doesn't make an obligation
  unknowable in 2024. We regrouped empirically on what baseline actually answered. Both splits
  are published.
- **112 judge verdicts still awaiting human spot-check.** Aggregates are provisional until reviewed.
- **Latency is reported, not claimed** — prior measurements conflict and we hold a no-speed-claim guard.
- No Carver licence fee is modelled anywhere — these are inference costs only.

---

## Asks

1. **Spot-check review** — 112 verdicts in `spot-check-queue.md`. Anyone disagreeing with the judge
   materially changes the numbers.
2. **Do we lead with "web is dominated" or with "grounding pays only where the model is blind"?**
   The second is more honest and more useful; the first is punchier.
3. **§06 replay box — delete or restate?** My call is delete.
4. **Is carver-domain-beats-carver-full a problem or a product insight?**
   It suggests sector routing before retrieval is worth real money.
5. **Worth extending?** The obvious gaps: more domains, harder tail questions, and a question set
   *not* sourced from our own corpus.

---

## Where the artifacts live

Branch `flux/docs-carver-whitepaper`, under `mastra-studio-demo/whitepaper/experiments/`

| file | what |
|---|---|
| `questions.json` | 26 questions + pre-registered keys (committed before any run) |
| `runs.jsonl` | 370 raw runs — usage, cost, latency, full answer text |
| `grades.jsonl` | every check verdict + judge rationale |
| `grades-v1-clockconfound.jsonl` | the superseded first pass, kept for audit |
| `analysis.py` | runs + grades → `frontier-data.json` |
| `../figures/frontier-data.json` | **single source of truth for every number in this deck** |
| `spot-check-queue.md` | 112 verdicts awaiting human review |

Whitepaper HTML is **untouched** — that's a separate, approved step.

---

## Appendix A — the 26 questions

Sourced from the corpus; answer keys written and committed **before any arm ran**.
Each scenario names no rule, deadline, or regulator — the obligation has to be noticed.
Full scenario text and keys: `experiments/QUESTION-SET-REVIEW.md`.

`blind` = the memory-only baseline could not answer it (empirical stratum).


**head-pre-cutoff** (8)

| id | domain | obligation the arm had to notice | source | blind? |
|---|---|---|---|---|
| q01 | medical-devices | Regulation (EU) 2023/607 extended the validity of MDD/AIMDD certificates and the MDR transitiona… | European Parliament and Co, 2023-03 |  |
| q02 | medical-devices | professional users must report serious incidents to Swissmedic AND to the supplier | Swissmedic, 2023-11 |  |
| q03 | crypto-assets | DAC8 requires crypto-asset service providers in the EU to report transactions of EU-resident cli… | Directorate-General for Ta, 2023-10 |  |
| q04 | crypto-assets | EBA ML/TF Risk Factors Guidelines were amended to insert crypto-asset specific risk factors and … | European Banking Authority, 2024-01 |  |
| q05 | state-lending | federally insured credit unions must notify the NCUA of a reportable cyber incident | National Credit Union Admi, 2023-08 |  |
| q06 | state-lending | the Second Amendment to 23 NYCRR Part 500 imposes an expanded cybersecurity programme on covered… | New York State Department , 2023-11 |  |
| q07 | child-safety | transparency obligations under GDPR Articles 12–14, as elaborated by the EDPB transparency guide… | European Data Protection B, 2018-04 | **yes** |
| q08 | child-safety | data protection by design and by default under GDPR Article 25 | European Data Protection B, 2020-10 |  |

**head-post-cutoff** (10)

| id | domain | obligation the arm had to notice | source | blind? |
|---|---|---|---|---|
| q09 | medical-devices | device registration in swissdamed becomes mandatory | Swissmedic, 2026-03 |  |
| q10 | medical-devices | mandatory Unique Device Identification labelling and data submission to the Australian UDI Datab… | Therapeutic Goods Administ, 2026-06 | **yes** |
| q11 | medical-devices | manufacturers must give advance notice of an interruption or permanent cessation of supply that … | ANSM, 2026-05 | **yes** |
| q12 | crypto-assets | EMT-related crypto-asset services count as payment services and require payment-institution auth… | Autorité de Contrôle Prude, 2026-02 |  |
| q13 | crypto-assets | stablecoin issuers recognised as systemic by HM Treasury fall under joint Bank of England and FC… | Bank of England, 2026-06 |  |
| q14 | crypto-assets | only entities authorised under MiCA by an EU competent authority may provide crypto-asset servic… | Czech National Bank, 2026-07 |  |
| q15 | state-lending | federal law preempts the Illinois Interchange Fee Prohibition Act for national banks and federal… | Office of the Comptroller , 2026-04 | **yes** |
| q16 | state-lending | updated disaster planning, preparedness and response requirements, including filings | New York State Department , 2026-05 |  |
| q17 | state-lending | FDIC official digital sign display requirements and non-deposit product signage on digital chann… | Federal Deposit Insurance , 2026-01 | **yes** |
| q18 | child-safety | prior consent of the EDPS is required before dismissing a DPO before the end of their term | European Data Protection S, 2026-02 |  |

**tail-silent-trigger** (5)

| id | domain | obligation the arm had to notice | source | blind? |
|---|---|---|---|---|
| q19 | medical-devices | a field safety notice affects the catheters the department uses — they fail authentication after… | Inspectie Gezondheidszorg , 2026-05 |  |
| q20 | medical-devices | an urgent field safety notice requires a mandatory software upgrade — this is not a deferrable u… | BfArM - Federal Institute , 2026-03 | **yes** |
| q21 | medical-devices | a field safety notice changed the validated sterilisation parameters for these products | Integra LifeSciences Corpo, 2026-06 | **yes** |
| q22 | medical-devices | a field safety notice requires a specific clinical workaround and a software update | Federal Institute for Drug, 2026-05 | **yes** |
| q23 | crypto-assets | Louisiana Act 510 (HB 582) changed deferred presentment and small loan limits | Office of Financial Instit, 2026-07 | **yes** |

**reuse** (3)

| id | domain | obligation the arm had to notice | source | blind? |
|---|---|---|---|---|
| q24 | crypto-assets | MiCA CASP authorisation is required; the transitional regime ends | various EU competent autho, 2026 | **yes** |
| q25 | medical-devices | Swiss device registration in swissdamed becomes mandatory | Swissmedic, 2026-03 |  |
| q26 | child-safety | age assurance and minors' protection obligations across the three named jurisdictions | various, 2026 |  |

---

## Appendix B — accuracy per question, per arm

Mean of 3 repeats. A question scores **0** for an arm if it failed either must-pass
precision check (`cite-real`, `no-fabricated-obligation`) — a confident hallucination
scores zero, it does not score partial credit.

| id | stratum | blind? | baseline | web | carver-full | carver-domain |
|---|---|---|---|---|---|---|
| q01 | pre |  | 58% | 100% | 100% | 100% |
| q02 | pre |  | 58% | 100% | 33% | 33% |
| q03 | pre |  | 88% | 100% | 67% | 100% |
| q04 | pre |  | 86% | 33% | 100% | 67% |
| q05 | pre |  | 83% | 100% | 67% | 92% |
| q06 | pre |  | 88% | 100% | 92% | 33% |
| q07 | pre | **blind** | 0% | 62% | 33% | 100% |
| q08 | pre |  | 75% | 88% | 92% | 96% |
| q09 | post |  | 71% | 92% | 100% | 100% |
| q10 | post | **blind** | 29% | 62% | 67% | 67% |
| q11 | post | **blind** | 29% | 100% | 100% | 100% |
| q12 | post |  | 88% | 33% | 100% | 67% |
| q13 | post |  | 88% | 100% | 100% | 100% |
| q14 | post |  | 88% | 100% | 100% | 100% |
| q15 | post | **blind** | 33% | 33% | 100% | 92% |
| q16 | post |  | 54% | 92% | 100% | 100% |
| q17 | post | **blind** | 21% | 100% | 88% | 88% |
| q18 | post |  | 88% | 100% | 33% | 67% |
| q19 | tail |  | 56% | 100% | 100% | 100% |
| q20 | tail | **blind** | 29% | 62% | 100% | 100% |
| q21 | tail | **blind** | 0% | 67% | 100% | 100% |
| q22 | tail | **blind** | 0% | 100% | 100% | 100% |
| q23 | tail | **blind** | 24% | 100% | 100% | 0% |
| q24 | reuse | **blind** | 48% | 0% | 67% | 67% |
| q25 | reuse |  | 86% | 57% | 100% | 95% |
| q26 | reuse |  | 86% | 67% | 0% | 33% |
| **mean** | | | **56%** | **79%** | **82%** | **81%** |

**Reading it:** the arms separate on the `blind` and `tail` rows and cluster everywhere else —
the deck's central claim, question by question.

**But look at the variance before trusting the means.** Every arm has questions it falls over on:
Carver scores 33% on q02 and q18 where web scores 100%; carver-full scores 0% on q26; carver-domain
scores 0% on q23 while carver-full scores 100% on the same question; web scores 0% on q24 and 33% on
q04, q12 and q15. Those are not rounding — they are whole questions lost, usually to a must-pass
precision failure.

With 26 questions and 3 repeats, a single question swings a pooled mean by ~4pp. **The per-arm means
on slide 7 are separated by 1-3pp between the three retrieval arms** — which is inside that noise.
The honest reading is that carver-full, carver-domain and web are *not* reliably distinguishable on
overall accuracy on this set; what IS robust is the cost gap, the `blind`/`tail` gaps, and baseline's
structural inability to cite.

