# Continuing — status and how to pick this up

Written 2026-07-21 on `feat-mastra-guardrail-port`. Read this before touching anything; it is the
short version of a long search that has mostly produced negative results, and those negatives are
the most valuable thing here. `docs/DEMO.md` has the full record.

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

## What was built for it

Three new arms, registered in `src/mastra/index.ts` (now 11 agents total):

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

## Next step

Search the corpus for **persona-triggered obligations that changed recently**, then re-run the
consumer framing against one. Concretely:

```bash
cd src/mastra/public
sqlite3 enforcement.db "SELECT json_extract(metadata,'\$.date'), json_extract(metadata,'\$.title')
  FROM enforcement WHERE json_extract(metadata,'\$.updateType')='final rule'
  AND json_extract(metadata,'\$.date') > '2025-06-01' ORDER BY 1 DESC LIMIT 40;"
```

Be warned: run as-is on 2026-07-21, that query returned mostly institutional plumbing — joint data
standards under the Financial Data Transparency Act, Designated Contract Market rules, Form X-17A-5
amendments. Those bind *firms*, not personas, so none of them work as a persona trigger. The recent
`final rule` population may simply not contain a consumer-facing obligation, in which case widen to
`guidance` and `interpretive rule`, or accept that this line is exhausted too.

A candidate needs all three: (a) it is triggered by a persona attribute rather than by the question,
(b) it changed after the model's training cutoff, (c) `keyRequirements` on the record is populated
and specific. If a candidate fails (c), the Carver arm will hedge exactly as it did on FCRA above.

**Kill the idea fast if it deserves killing.** The cheap falsification is the counterfactual swap:
hold the request fixed, change one persona attribute, and see whether the output changes. If CA emits
identical text across personas, the annotations are doing no work and this whole line stops.

## Corpus facts worth knowing before you plan

- `enforcement.db` — 6,168 records, **100% US federal**: FTC 1936, SEC 1353+978+150+70 (name not
  canonicalised), CFTC 1117+117, CFPB 443. No state regulators.
- **There is no `jurisdiction` field** on the trimmed records. Jurisdiction is only implicit in
  `regulator`. The user's Colorado/California/NY axis is not in the data and cannot be faked.
- `keyRequirements` is populated on 5,541 of 6,168 records (90%). This is the structured obligation
  layer and it is the most under-used asset in the corpus — web search returns a document, Carver
  returns the obligations already extracted from it.
- Regulation B's codified sections are present as individual records (`§ 1002.6`, `§ 1002.9`,
  `§ 1002.10`, `§ 1002.12`, `§ 1002.13`, `§ 1002.15`, `§ 1002.101`).
- Term counts: `Military Lending` 8, `servicemember` 14, `Regulation B` 34, `ECOA` 14,
  `adverse action` 11, `accredited investor` 11, `elder` 10. **`MAPR` is 0** — so the Military
  Lending Act beat is dead on arrival; Carver cannot cite the 36% cap and web search finds it easily.
- The **financial fixture is still broken** and this is unresolved: `scripts/build-updates.mjs` uses
  `PER_OTHER = 3` with no quality filter, so Kenya CMA is represented by an ingested HTTP 403 page
  titled "Forbidden". 84 non-US updates are `website error`. Depth available vs exposed: Saudi CMA
  1,374→3, Central Bank of Ireland 619→3, Kuwait CMA 387→3, Ghana SEC 379→3. Raising `PER_OTHER` and
  dropping crawler junk is ~20 minutes and was never approved; the 403 pages are indefensible
  whatever we end up demoing.

## Hazards

- **Never give a Carver tool to a web-search agent.** `@mastra/core` silently drops function tools
  when mixed with provider-defined ones. It is a *warning, not an error*, so the agent looks healthy
  and retrieves nothing.
- **Warm up before demoing.** The first call of a session 504'd at 180s, then answered in 22s on
  retry. Send a throwaway message before anyone is watching.
- **Carver arm thrashes.** 112 `searchCarverEnforcement` calls in the institution run, 20 in the
  consumer run. There is a prior incident of 304 calls returning an empty answer. Scope questions
  tightly and watch the tool-call count — it will look bad on stage.
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
