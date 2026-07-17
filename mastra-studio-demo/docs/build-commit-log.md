# Original commit log — flux/mastra-studio-ui

The full commit messages from the build phase in `carver-adhoc`, reproduced verbatim.

This demo was promoted to `carver-demos` as a **clean copy**, so these commits do not exist in
this repo's history, and the branch they came from has been deleted. The messages carry the
reasoning behind decisions that the code alone doesn't explain — why the acronym join exists,
why jurisdiction is mandatory, why the baseline isn't sandbagged — so they are kept here
rather than lost.

Hashes refer to the deleted `carver-adhoc` branch and will not resolve.

For the distilled version, read [`BUILD-NOTES.md`](BUILD-NOTES.md) instead.

---

## 7d0159c ✨ feat: minimal Mastra Studio project (hello-mastra)
Scaffolded via `npm create mastra@latest -- --default` and stripped to one
agent + one trivial tool, so Studio runs locally with a visible tool call in
the trace view. First Node/TypeScript project in this repo; self-contained
under projects/ per the one-folder-per-effort convention.

- helloAgent, model "openai/gpt-5.6-sol" (model-router string, no @ai-sdk dep)
- wordCountTool, a createTool with Zod in/out schemas
- storage + observability retained: Studio's Traces view requires an
  observability storage backend, else MastraStorageExporter self-disables
- dropped the wizard's weather agent/tool/workflow/scorers and the now-unused
  @mastra/duckdb, @mastra/evals, @mastra/memory

Verified end-to-end: agent answers and the trace shows
agent_run -> model_generation(gpt-5.6-sol) -> tool_call(wordCountTool) -> text.


## 87ddc06 ✨ feat: vendor Carver topic fixture for the grounded agent
Joins gics_classifications.json (this repo) with topic_catalog.csv
(carver-showcase, build time only) on topic_id to recover acronyms and
jurisdictions, then selects a deterministic ~150-record subset.

Why the join: the classification file has no acronym field, so "FCA" matched
zero records and "SEC" substring-matched 61 -- almost all false hits on
"Securities" (Alberta Securities Commission, ...). The catalog supplies the
acronyms that make lookup work.

Why jurisdiction is mandatory: 81 of 801 acronyms are ambiguous. SEC maps to 5
bodies (GH, NG, TH, US, TH); CBI to 5, including the Confederation of British
Industry alongside three central banks. Without jurisdiction the agent reports
Ghana's SEC as "the SEC" with full confidence.

The subset is a demo fixture, not a Carver dataset -- 150 of 1096 records,
chosen by rule (marquee bodies, whole ambiguous acronym families, substring
decoys, multilingual names, >=2 per sector, confidence mix, stratified fill).
Rebuild is byte-identical. The committed fixture is the only runtime data
dependency; carver-showcase is needed only to regenerate it.


## 96b8c5c ✨ feat: contrast demo — grounded vs ungrounded agent
Two agents in Studio, identical except for one variable: access to Carver's
topic taxonomy. Same model, same base instructions (shared via
base-instructions.ts so the prompts cannot drift apart and quietly invalidate
the comparison).

- baselineAgent  "Baseline Agent (no data)"  — no tools, answers from memory
- carverAgent    "Carver Agent (grounded)"   — searchCarverTopics over the fixture

The baseline is not sandbagged: it is not told it lacks data, nor told to
refuse. It does what a bare LLM does, which is the point.

searchTopics uses best-tier-wins matching (exact acronym > exact name > prefix
> substring): the most precise tier that matches is the entire answer. TDD
surfaced why this matters — with tier-blind matching "SEC" returned 19 records
(5 real SEC bodies + 14 "Securities" substring hits). Now it returns exactly 5.

Verified live, same question to both:
  "What sector is the SEC in?"
    baseline → "oversees U.S. securities markets"     [0 tool calls]
    carver   → ambiguous across US/GH/NG/TH, Financials /
               Investment Banking & Brokerage, high    [1 tool call]
  "What sector is the Reykjavik Bicycle Authority in?" (invented body)
    baseline → "public transportation and urban mobility sector"  ← hallucinated
    carver   → "isn't in Carver's regulatory taxonomy"

Also: 10 unit tests over the pure matcher (node --test, no runner dep);
deleted helloAgent/wordCountTool scaffolding; tsconfig allowImportingTsExtensions
so node's type stripping and the bundler agree on .ts imports.


## b3053dd 📝 docs: document the contrast demo and session findings
README rewritten around the two-agent contrast, with the demo table, why the
acronym join and jurisdiction are load-bearing, and an explicit note that the
150-record file is a fixture rather than Carver coverage.

Also tracks .flux/ session state (migrated from the legacy .claude/.sessions/
copies, originals left untouched).


## 0452869 ✨ feat: vendor Carver regulatory updates + searchUpdates matcher
Adds the "what changed, when, why" layer the previous design called out of
scope. Most of the annotation dataset postdates any model's training cutoff
(125,882 records dated 2026), which turns the demo's soft precision contrast
into a hard epistemic wall: the baseline cannot know this, at all.

- scripts/build-updates.mjs streams carver-showcase's 1.7 GB annotations.jsonl
  and keeps a recent-first slice for the 145 topics that join our existing
  fixture -> data/carver-updates.json (1,002 records, 1.1 MB, deterministic).
- Selection is neutral (most recent per topic), not matched to the demo
  questions -- a fixture rigged to a script collapses on the first adjacent
  question.
- MARQUEE moves to scripts/marquee.mjs so both builders cannot drift; verified
  the topics fixture rebuilds byte-identical after the extraction.
- searchUpdates delegates name resolution to the existing tested searchTopics
  matcher, so acronym handling and cross-jurisdiction ambiguity are inherited
  rather than reimplemented.
- 11 new tests (21 total), typecheck clean.

Spec: projects/hello-mastra/docs/superpowers/specs/2026-07-16-carver-updates-tool-design.md


## 4b69fd1 ✨ feat: searchCarverUpdates tool + fix false-absence in the matcher
Wires the updates tool onto carverAgent (now two tools) and broadens the
shared prompt.

The matcher fix came out of live verification, not review. Asked about "the UK
Financial Conduct Authority", the grounded agent replied that the FCA "isn't
listed in Carver's dataset" -- false; it has 30 records. Agents pass through
however the user phrased it, and the tiers only ever tested whether a record
name contains the query, never the reverse, so any query more specific than the
stored name missed silently.

False absence is the worst possible failure for a tool whose entire promise is
admitting what it doesn't have -- strictly worse than a wrong answer, because it
looks like integrity. Fixed with a reverse-containment tier, placed last so it
can never pre-empt a more precise match (asserted by test: "SEC" still returns
exactly 5).

BASE_INSTRUCTIONS broadens to cover recent activity as well as sector. It was
scoped to sector lookup only; leaving it would have made the baseline fail a
question its own prompt never invited -- sandbagging, which would invalidate the
comparison. The wall must be the training cutoff, not our wording.

23 tests pass, typecheck clean, both fixes verified live.


## 3d39ea2 📝 docs: document the staleness contrast and the false-absence lesson
README now reports what live testing actually showed, not what the design
predicted. The headline beat changed: on BIS/stablecoins the baseline cites
real 2023-24 papers rather than hallucinating -- it is confident, accurate and
two years stale, which is the failure that actually ships. Fabrication only
appears for an invented body.

Also records that the baseline often refuses honestly ("that period has not
occurred yet") instead of inventing. A demo claiming "the baseline always
hallucinates" would be false and would collapse under one question.

Adds the false-absence gotcha: 23 unit tests missed it; one live question found
it.


## f3ee8cc 📝 docs: add demo run-sheet
Four beats in a fixed order, every query and response verified live against the
current build (post prompt-broadening and post second tool -- the earlier
verifications were run under a different config and are not reused).

Includes the framing for each beat, the phrasing that avoids the baseline's
clarifying-question dodge, and explicit "do not oversell" notes where the
baseline's behaviour is more honest than the pitch would like.


