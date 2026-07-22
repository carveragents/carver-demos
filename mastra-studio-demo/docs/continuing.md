# Continuing — status and how to pick this up

Written 2026-07-21, extended 2026-07-22, on `feat-mastra-guardrail-port`. Read this before touching
anything; it is the short version of a long search that has mostly produced negative results, and
those negatives are the most valuable thing here. `docs/DEMO.md` has the full record — including the
cross-domain mini-suite that closed the "better answers" question for the eleventh time and
quantified the operational alternative.

## The question we are trying to answer

Can we demonstrate that a **Carver-grounded agent (CA)** beats a **baseline + web-search agent
(BWSA)** on `openai/gpt-5.6-sol`, when both have access to fresh data?

The constraints the user set, which have held up under testing:

- BWSA cannot be beaten on pure reasoning — current models are good at it.
- BWSA cannot be beaten on guardrails — current models are trained for them.
- Both arms have live data. CA's claim has to rest on *structured intelligence over that data*.

## What has already failed — do not rebuild these

Eight probes across three domains (regulatory, cybersecurity, investment). Full detail in
`docs/DEMO.md` under "The comparability thesis", "Rejected: reasoning beats", and "What is
actually left, after eight probes across three domains".

| Probe type | Outcome |
|---|---|
| Lookup / recency | tie |
| Aggregate count | **CA wins** — 67 in 10.8s vs web's 83.5s "I can't give a defensible count" |
| Correlation / coverage | web wins, 13 bodies to 7 |
| Divergence reasoning | web wins |
| Base-rate reasoning | web wins, and correctly caught that CA's "spike" was six agencies covering one campaign |
| Ambiguous acronym (CMA) | baseline also disambiguates unprompted; CA's edge is thin |
| Obligation questions, obscure non-US regulators | web wins decisively |

**The structural reason lookup beats lose:** the question contains its own retrieval key. "What did
Ghana SEC publish about X" *is* the search string, so web search wins by construction. Any new beat
must be one where the user never names the thing that needs retrieving.

## The current hypothesis (user's framing, 2026-07-21)

Stop testing the median query. Test the **edges**, where a *persona* silently triggers a regulatory
obligation nobody mentioned. The user's examples: booking a doctor's appointment for a spouse where
proxy consent rules vary; a loan denial where required disclosure differs by jurisdiction.

Why this is structurally better than everything above: the obligation is never named in the query.
For BWSA to get it right it must first know a rule exists, then guess its name, then search. It
fails at step one **silently**, and the failure looks like success.

Two design rules that came out of this and should be kept:

1. **Inject the persona as a system message, never in the user turn.** A signed-in user is realistic,
   and it stops the persona acting as a search string. Both arms get it equally.
2. **Score mechanically.** The rig regex-scores required elements so the verdict does not depend on
   anyone's reading of the transcripts.

## What was built for it (the original lending probe — superseded by the mini-suite below)

Three lending arms, registered in `src/mastra/index.ts` (the registry now holds 16 agents — these
three, the cross-domain mini-suite's five, and the earlier regulatory/investment/cyber sets):

| Agent id | Tools |
|---|---|
| `lending-baseline-agent` | none |
| `lending-websearch-agent` | `webSearch` |
| `lending-carver-agent` | `searchCarverEnforcement` |

`src/mastra/agents/lending-base-instructions.ts` is shared verbatim and deliberately says nothing
about regulation or compliance — priming any arm to "consider applicable law" would answer the
question in the prompt. The search-trigger clause in the websearch and Carver arms is **worded
identically**; if it drifts, a measured gap could be phrasing rather than data.

`scripts/persona-probe.mjs` runs one scenario across all three arms under two deployment framings.

```bash
npm run dev                              # Studio on :4111, wait ~25s
node scripts/persona-probe.mjs both      # or: consumer | institution
```

## What it measured

Scenario: application 4471 declined, applicant is 39, Colorado, file complete **34 days** — four
days past Regulation B's 30-day notification deadline. Two obligations planted, neither named.

| Framing | Baseline | Web search | Carver |
|---|---|---|---|
| **Consumer** (applicant asks) | **1/5** · 22.6s | 3/5 · 14.2s · 16 searches | **4/5** · 15.9s · 20 calls |
| **Institution** (officer drafts) | 3/5 · 21.2s | **4/5** · 54.3s · 58 searches | 4/5 · 60.1s · 112 calls |

**Consumer framing is the one to keep.** It is the only cell with a monotonic spread, and the
baseline's failure is demo-legible: asked by the applicant himself, it gave the decision and factors
then said "your formal adverse-action notice will include these reasons" — never telling him he has
a *right* to those reasons, never noticing the lender is out of time. Carver caught both and cited
`§ 1002.9` at the canonical `consumerfinance.gov/rules-policy/regulations/1002/9/`.

**Institution framing collapses and should be dropped.** Web search produced the best artifact of all
six runs (FCRA credit-score disclosures, the key-factor-codes distinction, CFPB Form C-2). Carver
ended its own draft with "The Carver search did not return sufficiently specific FCRA notice
requirements to validate that section" — correct, but a corpus gap said out loud.

## The diagnosis — read this before proposing the next scenario

**The obligation was badly chosen, and the institution row proves it.** The tool-less baseline drafted
a near-complete adverse action notice from memory in 21 seconds: ECOA paragraph, 60-day report
rights, CRA block. Regulation B's model forms have been stable since 1977 and saturate the training
data.

So the scenario violated its own premise. The framing predicts a gap when the agent *doesn't know a
question was asked* — but every arm knew.

The framing is not refuted. The discriminating variable is not persona alone; it is
**persona × an obligation the model's memory is stale on**. That means a *recent change*, where the
baseline recites the superseded rule confidently and web search retrieves whichever version ranks
highest. It is also the only axis where a curated, dated corpus is structurally advantaged rather
than incidentally so.

## Next step — DONE. The persona line went cross-domain and confirmed the operational pitch (2026-07-22)

The persona line was widened (per the user) beyond consumers to any **silent trigger** — an actor
attribute that fires an unnamed obligation — and beyond finance to the full corpus. A three-domain
mini-suite (crypto MiCA-CASP, medical-device swissdamed, minors age-assurance) was built and
measured. **Full write-up: `docs/DEMO.md` → "Cross-domain silent-trigger mini-suite".** Headline:

- **Content: web search reaches parity (5/5 vs 5/5) in every domain.** The "unretrievable obscure
  source" theory was refuted — web search found Banca d'Italia, Swissmedic (German), the Gazzetta
  Ufficiale, SB243/976, Ofcom, the ICO, accurately and in-language.
- **Operational: Carver wins, and it's now quantified.** Same answer, ~30% faster (up to 2×), tighter
  latency, equal-or-lower token burn (40% less on device), and more reproducible (web dropped to 3/5
  on one identical-prompt device run). Baseline is 20× cheaper on tokens but capped at 4/5 (can never
  cite a link) and dips unpredictably.

This was the eleventh probe to land on the operational conclusion — but the **twelfth found the one
exception.** See below.

**How to re-run:** `npm run dev`, then `node scripts/trigger-probe.mjs all 3`. The three sector
fixtures are gitignored; rebuild with `npm run build:domain -- <crypto-assets|medical-devices|child-safety> ../../carver-showcase/data/annotations.jsonl`.

## The ONE content win — state-lending counterfactual swap (probe 12, 2026-07-22)

The user's original instinct was right after all. A **home loan denied by an automated model**, with
the applicant's **state** swapped CO/CA/NY, is the one case where Carver beats **both** baseline and
web search on content: it surfaces Colorado's AI Act (SB 24-205/SB 26-189, ADMT duties) and
California's Holden Act, which baseline and web both miss (**web 0/5 on Colorado** — it searches
generically and never looks for a state AI statute). It **scales**: with the obligation embedded in a
7,142-record haystack of real US consumer-lending regulators, the CO AI Act still ranks **#1 of 7,146**
for a situation-aware query. Full write-up: `docs/DEMO.md` → "The state-lending counterfactual swap".

**Three caveats that must travel with this result:**
1. It runs on **4 hand-curated records** (`data/state-lending-records.json`), NOT the crawled corpus,
   and the win is **100% dependent on them** — measured: drop them and re-run against the 7,142 real
   records alone and the Carver arm collapses to parity (MISS on CO *and* CA). CO AI Act is 0 records;
   CA Holden Act is *named* in 5 DFPI reporting bulletins but the obligation isn't captured
   (present-in-name ≠ usable-obligation); only the 2 *state* records are load-bearing (the 2 federal
   ones are redundant with real CFPB/FTC coverage). Proof-of-concept of what coverage *unlocks*, not a
   shipping capability. Full detail: `docs/DEMO.md` caveat 1.
2. Retrieval needs a **situation-aware query** (state + automated); the agent supplies that from its
   system-message context. On the bare user words the CO record does not rank top-6.
3. The curated records are **REVIEW-REQUIRED** (Colorado requirements lean partly on secondary
   summaries; verify against the primary statute).

To get these obligations into the corpus organically (for the data team): what institutions and
canonical URLs to add is in **`docs/corpus-gaps-for-jurisdiction-demos.md`**.

**How to re-run the swap:** `npm run dev`, then `node scripts/state-lending-probe.mjs 1`. Rebuild the
index (gitignored) with `npm run build:domain -- state-lending ../../carver-showcase/data/annotations.jsonl`
then `npm run build:curated -- state-lending data/state-lending-records.json`.

## Corpus facts worth knowing before you plan

- **The real corpus is `carver-showcase/data/annotations.jsonl` — 242,512 records, multi-jurisdiction**
  (US federal + state, plus EU/UK/CH/AU/IN/etc.), with `output_data.reconciled_published_date.date`
  (a real published date), and a rich structured layer: `metadata.actionables` (by change-type),
  `reg_references` (rules + statutes), `impacted_business.{industry,jurisdiction}`, `critical_dates`,
  `penalties_consequences`. Query it via node + `@libsql/client` or stream the JSONL — **`sqlite3`
  CLI is not installed here.**
- **`enforcement.db`/`carver-updates.json` are heavily TRIMMED slices** (6.4k / 1k records) of that
  corpus, selected by a small topic/regulator set. The earlier "100% US federal, no jurisdiction,
  corpus exhausted" claim in prior versions of this file was an artifact of reading the trimmed
  fixture — it does **not** hold for the full corpus. The full corpus has a `jurisdiction` field and
  state/international bodies.
- `impact_summary.key_requirements` (the fixture's obligation field) is populated on ~90%+ of records
  across sectors — crypto 2591/2749, device 5633/6316, minors 632/670. This is the most under-used
  asset: web search returns a document, Carver returns the obligations already extracted from it.
- To add a demo domain: neutral **sector** selector via `impacted_business.industry` in
  `carver-domains.json` (`industryAny`), then `npm run build:domain`. Both `crypto-assets` and
  `medical-devices` and `child-safety` were built this way; the pattern is proven.
- The **financial fixture is still broken** (separate from the mini-suite): `scripts/build-updates.mjs`
  uses `PER_OTHER = 3` with no quality filter, so Kenya CMA is an ingested HTTP 403 page titled
  "Forbidden" and 84 non-US updates are `website error`. Only relevant if you revive scenarios 1/2.

## Hazards

- **Never give a Carver tool to a web-search agent.** `@mastra/core` silently drops function tools
  when mixed with provider-defined ones. It is a *warning, not an error*, so the agent looks healthy
  and retrieves nothing.
- **Warm up before demoing.** The first call of a session 504'd at 180s, then answered in 22s on
  retry. Send a throwaway message before anyone is watching.
- **Carver arm thrashes — now capped on the mini-suite arms.** The three `*-carver-agent`s carry
  `defaultOptions: { maxSteps: 8 }`, verified to stop an interactive call at ≤8 steps. The
  `lending-carver-agent` and older arms are **not** capped and still thrash (112 calls seen, a prior
  incident of 304 returning empty). The cap bounds *steps*, not parallel tool-calls-per-step: a "be
  thorough, check everything" prompt still fired ~22 parallel searches over 4 steps (140k tokens).
  Keep demo prompts naive, and add the same cap to any new grounded arm.
- Studio keys agents by their kebab-case `id`, not the camelCase registry key.
- Model router strings use a slash: `openai/gpt-5.6-sol`.

## Doctrine that constrains all of this

- **"Cherry-pick the questions, never the fixture."** Selection stays neutral — by body, sector, or
  jurisdiction — *never* by matching a demo question.
- Never ship a fabricated, paraphrased, or synthesised record. Never ship an unreviewed one.
- `../carver-showcase` is **read-only**.
- Record rejected beats in `docs/DEMO.md` so nobody rebuilds them. This has already paid for itself
  several times.
- Measure, don't assert. Every claim in this file came from a run, and the runs that went against the
  thesis are written down at the same volume as the ones that went for it.
