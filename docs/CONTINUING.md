# Continuing — status and how to pick this up

Written 2026-07-28 on `main`. The next piece of work is a **demo video** showing that a
Carver-grounded agent answers a loan-denial question correctly where a memory-only agent and a
live-web-search agent both fail — using the state-lending applicant scenario in
`mastra-studio-demo/`.

The demo itself is **built, committed, and verified working**. Nothing needs to be rebuilt. What
does not exist yet is the video: no script, no storyboard, no recording, no takes.

Fuller records, in order of usefulness:
- `mastra-studio-demo/docs/DEMO.md` — the run sheet, from line ~961 ("The state-lending
  counterfactual swap") through the beat-by-beat presenter script at ~1054. **Read this before
  anything else.** It is the presenter's script and it is good.
- `mastra-studio-demo/docs/corpus-gaps-for-jurisdiction-demos.md` — why the demo needs curated
  records, and what the data team would have to ingest to make it work organically.
- `docs/LESSONS.md` — project-wide lessons.

## The question we are trying to answer

Can we produce a short video that makes one narrow, **true** claim land: that when a loan is denied
by an automated model, the obligation owed to the applicant varies by their **state**, and only the
Carver-grounded agent surfaces it — because web search never thinks to look for a state AI statute.

The constraint that governs everything: **the claim must survive a hostile viewer.** This demo rests
on hand-curated records (see Hazards). A video that implies "Carver's corpus already does this today"
is overclaiming and will not survive contact with anyone who checks.

**Style, framing, and presentation direction have NOT been given yet.** The user will supply them in
the next session. Do not invent a visual style, pick a voiceover tone, or start recording before
asking. What you can usefully do now is confirm the demo runs on your machine and read the run sheet.

## What has already failed — do not rebuild these

This demo is the **one** content win out of **twelve** probes. Eleven others were run and failed.
Do not go looking for a better scenario — that search has been done, at length, and this is the
survivor. From `DEMO.md`:

| approach tried | outcome | structural reason it failed |
|---|---|---|
| Crypto / MiCA CASP authorisation scenario | Web search reached **parity** with Carver | The obligation is publicly retrievable and heavily covered; web finds it easily |
| Medical-device / swissdamed registration | Parity | Same — public, well-indexed obligation |
| Online child-safety / age assurance | Parity | Same |
| Persona-obligation probe (lending trio) | Did not discriminate | The persona did not trigger a distinct obligation |
| Investment / enforcement-signal advice | Parity | Public enforcement actions are exactly what web search is good at |
| **State-lending applicant swap** | **WIN** | The obligation is recent, jurisdiction-specific, and *unnamed in the question* — web does not know to search for it |

The generalisable lesson, already paid for: **"better answers" is not available against
`gpt-5.6-sol` on any publicly-retrievable obligation.** The only content win is an unnamed, recent,
jurisdiction-specific obligation. Everywhere else the pitch is operational (cost, reproducibility).

Two further dead ends, both measured:

1. **Dropping the curated records and relying on the real corpus alone.** Re-run against the 7,142
   real records without the 4 curated ones and the Carver arm **collapses to parity** — MISS on
   Colorado *and* California. Colorado's AI Act is 0 records in the corpus. California's Holden Act
   appears by *name* in 5 DFPI records, but they are annual reporting-deadline bulletins, not the
   Fair Lending Notice obligation. **Present-in-name ≠ present-as-a-usable-obligation.**
2. **Only the 2 *state* records are load-bearing.** The 2 federal curated records (Reg B, FCRA) are
   redundant — the federal floor survives from the real CFPB/FTC records already in the corpus.

Also relevant, from a separate 370-run experiment on this repo (`carver-whitepaper/`): a full-corpus
Carver arm over all 229,287 records was **not** better than the curated per-sector slice on general
accuracy. So "just point it at the whole corpus" is not a fix for the gap above — it has been tried
on a different question set and did not help.

## Current state

Everything below is committed on `main` and pushed.

**Agents — three arms, registered in `mastra-studio-demo/src/mastra/index.ts`:**

| file | arm | tools |
|---|---|---|
| `agents/lending-status-baseline-agent.ts` | baseline | `lookupApplicant` |
| `agents/lending-status-websearch-agent.ts` | web search | `lookupApplicant` + `webSearch` |
| `agents/lending-status-carver-agent.ts` | Carver | `lookupApplicant` + `searchCarverStateLending` |
| `agents/lending-status-instructions.ts` | shared prompt for all three | — |

All three share one prompt and one trigger clause. **Retrieval is the only variable.** If you change
the prompt, change it in the shared file or the comparison is invalid.

**Tools:** `tools/lookup-applicant-tool.ts` (auth/CRM stand-in; carries the applicant's state),
`tools/carver-state-lending-tool.ts` (semantic search over the state-lending index).

**Data:** `data/state-lending-records.json` — the 4 hand-curated obligation records.

**Scripts:** `scripts/lending-status-probe.mjs` (the scorecard — content + tokens + cost),
`scripts/build-domain-index.mjs`, `scripts/build-curated-index.mjs`.

Other `lending-*` files exist (`lending-baseline-agent.ts`, `lending-carver-agent.ts`,
`lending-websearch-agent.ts`, `lending-base-instructions.ts`, `state-lending-carver-agent.ts`).
These are **superseded** by the `lending-status-*` trio and are deliberately **not registered**.
Do not use them for the video.

**Not started:** video script, storyboard, screen-recording setup, any recorded take.

## How to run it

Assume a clean machine. Requires `OPENAI_API_KEY` and the sibling `carver-showcase` repo checked
out next to this one (for the corpus snapshot).

```bash
cd mastra-studio-demo
npm install                                   # ~1 min

# .env with the API key — never commit this file
printf 'OPENAI_API_KEY=sk-...\n' > .env

# Build the index. BOTH commands are required, in this order.
npm run build:domain  -- state-lending ../../carver-showcase/data/annotations.jsonl
npm run build:curated -- state-lending data/state-lending-records.json

npm run dev                                   # Studio on :4111, ready in ~25s
```

`build:domain` costs money (it embeds ~7,142 records with `text-embedding-3-small`) and takes a few
minutes. `build:curated` adds the 4 curated records to the same index and is near-instant.
**Restart `npm run dev` after building** or the agent reads a stale index.

Verify before recording anything:

```bash
node scripts/lending-status-probe.mjs         # 3 applicants x 3 arms, ~4 min, a few $
```

**I ran this on 2026-07-28 and it reproduced exactly** (against a server on `:4112`; pass
`MASTRA_URL` if yours is not on `:4111`). Expected output:

```
arm                              CO (CO-1001)  CA (CA-1001)  NY (NY-1001)
lending-status-baseline-agent    miss ✗        miss ✗        clean ✓
lending-status-websearch-agent   miss ✗        miss ✗        clean ✓
lending-status-carver-agent      YES ✓         YES ✓         clean ✓
```

If the Carver row is not `YES YES clean`, the curated records are missing from the index — re-run
`build:curated` and restart the server. Confirm with:

```bash
node -e "import('@libsql/client').then(async({createClient})=>{
  const c=createClient({url:'file:src/mastra/public/state-lending.db'});
  console.log((await c.execute(\"SELECT COUNT(*) n FROM stateLending\")).rows[0].n, 'records');
})"
# expect 7,146 — that is 7,142 real + 4 curated. 7,142 alone means build:curated did not run.
```

## What was measured / what happened

Verified live on 2026-07-28, three arms x three applicants:

**Content** — Carver `YES / YES / clean`; baseline and web search `miss / miss / clean`.
Web search has **never** surfaced the Colorado AI Act, across five separate runs. Given the identical
Colorado + automated-decision context it searches generically ("adverse action", "loan denial"), gets
the dominant federal result, and stops. **The failure looks like success** — that is the whole point
of the demo, and it is the single most important thing for the video to make visible.

**Cost per 1,000 runs** (gpt-5.6-sol rates, checked 2026-07-23):

| arm | cache-warm | cold | median tokens |
|---|---|---|---|
| baseline | $11.94 | $11.94 | 989 |
| web search | $77.68 | $120.50 | 18,800 |
| Carver | $50.09 | $50.09 | 5,908 |

Carver is 36% (warm) to 58% (cold) cheaper than web search, and cache-independent. Note web's figure
is a **floor** — it excludes OpenAI's internal web_search fetch/rank tokens, which are not reported.

**Ranking check:** for a situation-aware query ("automated model denies a home loan in Colorado") the
Colorado AI Act record ranks **#1 of 7,146**. The win survives being embedded in a realistic haystack
of real US consumer-lending regulators.

**Against the thesis:** see "What has already failed". Without the curated records the win vanishes
entirely. The demo proves *what jurisdiction-tagged coverage unlocks*, not a current capability.

## Next step

1. Run the setup and the probe above. Confirm you get `YES YES clean`. Do not script anything until
   you have seen it on your own machine.
2. Read `DEMO.md` from line ~1054 — it already contains a beat-by-beat presenter script (Beat 1 =
   Colorado, "the money shot"; Beat 2 = California, "not a fluke"; NY = the negative control). The
   video script should be an adaptation of this, not a fresh invention.
3. **Ask the user for style and presentation direction before writing the script or recording.**
   They said explicitly it would come in the next session. Decisions that are theirs, not yours:
   length, voiceover vs captions, live Studio capture vs edited screen recording, whether the cost
   numbers appear at all, and how prominent the curated-records caveat must be.
4. If you want something useful to prepare in the meantime: a **shot list** of exactly what has to be
   on screen for the claim to land — the applicant ID being typed, the `lookupApplicant` result
   showing the state (which the applicant never typed), and the three answers side by side.

**The single decision I would flag:** the honest caveat (hand-curated records) is awkward in a
marketing video but load-bearing for credibility. My recommendation is that the video makes a
narrower claim — "this is what jurisdiction-tagged regulatory data unlocks" — rather than implying
the capability ships today. Put that question to the user early; it changes the script.

## Data dependencies

- **Sibling repo `carver-showcase`** must be checked out next to this one:
  `../carver-showcase/data/annotations.jsonl`. It is ~1.9 GB. **Treat it as READ-ONLY.**
- The corpus snapshot moves. As of 2026-07-27 it was 249,328 records, snapshot date 2026-07-27.
  `build-domain-index.mjs` caps records at `SNAPSHOT_MAX = 2026-07-06`, so the state-lending index is
  ~7,142 real records regardless of minor snapshot drift.
- **`OPENAI_API_KEY`** is needed for both embedding (build) and inference (run). Ask the user; never
  commit it. `.env` is gitignored, and the commit script refuses to stage it.
- The built index `src/mastra/public/state-lending.db` (~59 MB) is a **gitignored build artifact** —
  it is not in the repo and must be built locally. `*.db` is ignored in
  `mastra-studio-demo/.gitignore`.
- **The scenario is dated January 2027 on purpose.** The applicant fixture carries decision date
  `2027-01-14`. The Colorado AI Act's automated-decision duty is operative 2027-01-01. This is not a
  stray future date — do not "fix" it. Frame it as "the law just took effect."

## Hazards

- **The applicant must never name the rule.** The whole contrast collapses if a presenter types
  "does Colorado's AI Act apply?" — web search finds it immediately. The applicant asks only about
  their loan status and gives an ID. The state arrives from `lookupApplicant`. Protect this in the
  video: it is the difference between a demo and a rigged demo.
- **The demo is 100% dependent on 4 hand-curated records**, which are **REVIEW-REQUIRED** (legal and
  data review, not yet done). The Colorado requirements lean partly on secondary summaries. Verify
  against the primary statute before any public-facing use.
- **Never ship fabricated, paraphrased, or synthesised records.** The curated 4 are grounded in cited
  primary sources; anything new must be too, and must be reviewed.
- Retrieval depends on a **situation-aware query**. On the bare user words ("loan declined, what
  next") the Colorado record does not rank top-6. The agent supplies the state + automated cue from
  its system context. Realistic, but it means the win rests on the agent searching *with the
  situation*, not on the corpus alone.
- `build:curated` is a separate step from `build:domain` and is easy to forget. Symptom: the Carver
  arm misses Colorado and California and the demo silently looks like a failure. Check the record
  count is 7,146, not 7,142.
- Restart `npm run dev` after any index build, or the agent reads the old index.
- Studio shows only registered agents. If you see more than the five registered on `main`, you are
  on the `flux/docs-carver-whitepaper` branch, which registers six extra measurement agents.

## Constraints and doctrine

- `../carver-showcase` is **READ-ONLY**.
- The 4 curated lending records are **REVIEW-REQUIRED** (legal/data) before any live or public demo.
- Never commit secrets. `.env` is gitignored; do not work around it.
- **Do not push or merge without an explicit request from the user.**
- All three arms share one prompt and one trigger clause. Change it in the shared file or not at all —
  divergent prompts invalidate the comparison and quietly turn the demo into a lie.
- Numbers shown anywhere must trace to a measurement, not to memory. The whitepaper next door keeps a
  single-source-of-truth JSON for exactly this reason; hold the video to the same standard.

## Related work in this repo (context, not required reading)

`carver-whitepaper/` on `main` holds a finished 370-run cost/accuracy experiment comparing four arms
(memory-only, web search, Carver full-corpus, Carver curated slice) over 26 questions, with an
internal deck at `carver-whitepaper/experiments/INTERNAL-DECK.md` (open `INTERNAL-DECK.html` to view
it as slides). Its raw run data lives on branch `flux/docs-carver-whitepaper`. Relevant to the video
only as a source of defensible cost numbers and as evidence that the accuracy claim needs care.
