# Carver-aware agent — design

**Date:** 2026-07-16
**Status:** awaiting review
**Project:** `carver-demos/mastra-studio-demo`
**Session:** `.flux/sessions/2026-07-16-190157-mastra-studio-ui.md`

## Goal

Demonstrate the value of plugging in a data source, by **contrast**: two agents in Studio,
identical in every respect except one, answering the same question side by side.

| Agent | Studio name | Carver data |
|---|---|---|
| `baselineAgent` | Baseline Agent (no data) | none — answers from model memory |
| `carverAgent` | Carver Agent (grounded) | `searchCarverTopics` tool over vendored data |

Scope is deliberately two agents and one tool. This is the smallest slice that shows the
difference a data source makes, and shows a real retrieval call in Studio's trace view.

## Why this is worth doing

Asked "what sector is 금융감독원 in?", a bare LLM guesses. The grounded agent returns
*Diversified Banks / Financials, confidence high* — traceable to a specific record in the
taxonomy produced by the `gics-topic-tagging` project. The trace shows exactly which record
was used.

The sharper case is ambiguity. Asked "what sector is the SEC in?", a bare LLM assumes the
US. The data says `SEC` matches **five** bodies in five jurisdictions. The grounded agent
surfaces that instead of guessing.

### The contrast must be honest

The two agents differ in **exactly one variable**: access to Carver data. Same model
(`openai/gpt-5.6-sol`), same base instructions, same phrasing of the question.

The baseline is **not** sandbagged. It is not told "you have no data" or "refuse to answer"
— that would produce a boring "I don't know" and prove nothing. It gets neutral, helpful
instructions and does what a bare LLM naturally does: answers fluently and plausibly, and
silently assumes the US SEC.

Equally, it is not rigged to fail. If the model happens to know a classification, it may
well be right — the demo's point is not that the baseline is *always* wrong, but that its
answers are **unverifiable, jurisdiction-blind, and untraceable**, while the grounded
agent's cite a specific record with a confidence and a jurisdiction. The trace view is what
makes that difference visible rather than rhetorical.

## Findings that shape the design

Established by probing the real data (not assumed):

1. **The live Carver API is unavailable.** `GET /api/v1/feeds/topics` with the
   `CARVER_API_KEY` from the repo-root `.env` returns **401 Invalid API key**. The key is a
   well-formed 32 chars, so it is expired or revoked. This design therefore uses local data
   only and makes no network calls.
2. **The `carver-feeds-skill` SDK is Python; this agent is TypeScript.** It cannot be
   reused. A live version would have to call the REST API directly via `fetch`
   (`X-API-Key` header, base `https://app.carveragents.ai`).
3. **Naive substring search is actively misleading.** `SEC` substring-matches 61 records —
   almost all of them hits on "**Sec**urities" (Alberta Securities Commission, Arkansas
   Securities Department). `FCA` substring-matches **zero**: the record is named "Financial
   Conduct Authority" and the classification file has no acronym field.
4. **Acronyms are recoverable by join.** `carver-showcase/data/topic_catalog.csv` has an
   `acronym` column and shares `topic_id` with the classification file. Join rate: 1060/1096
   (97%); 914 records (83%) have a non-empty acronym.
5. **Acronyms are ambiguous — 81 of 801 collide.** `SEC` → 5 bodies (GH, NG, TH, US, TH).
   `CBI` → 5 (Central Bank of Iceland/Iraq/Ireland, *and* the Confederation of British
   Industry). `CMA` → 5. `DOI` → 4. **Jurisdiction is therefore mandatory** in both the
   vendored records and the tool output; without it the agent reports Ghana's SEC as "the
   SEC" with full confidence.
6. **The classification data is sound.** All 1,096 records are `status: classified`, across
   two taxonomies (GICS 577 commercial, Carver-Gov 519 government), 19 sectors, confidence
   high 913 / low 111 / medium 72, and 349 records carry secondaries.

## Architecture

Three units, each independently understandable and testable.

```
data/carver-topics.json   ← vendored, committed (the only runtime data dependency)
        ↑ built once by
scripts/build-topics.mjs  ← joins classification + catalog, selects the subset
        ↓ read at startup by
src/mastra/tools/carver-topic-tool.ts  ← searchCarverTopics (pure matching + Zod schema)
        ↓ registered on
src/mastra/agents/carver-agent.ts      ← carverAgent   (tool)
src/mastra/agents/baseline-agent.ts    ← baselineAgent (no tool, same everything else)
        ↓ both registered in
src/mastra/index.ts       ← new Mastra({ agents: { baselineAgent, carverAgent } })
```

`src/mastra/agents/hello-agent.ts` and `src/mastra/tools/word-count-tool.ts` are **deleted**
— see Decisions.

### 1. Vendored data — `data/carver-topics.json`

Self-contained per the repo's one-folder-per-effort convention. No cross-project or
cross-repo reads at runtime; the demo works with `carver-showcase` absent.

Record shape (flat — the nested GICS `path` is collapsed to the three tiers the agent
actually reports):

```json
{
  "topicId": "3ad72781-0587-4468-b0ed-966886e8bbe4",
  "name": "한국은행",
  "acronym": "BOK",
  "jurisdiction": "KR",
  "system": "GICS",
  "sector": "Financials",
  "industry": "Financial Services",
  "subIndustry": "Specialized Finance",
  "confidence": "high"
}
```

`acronym` is `""` where the source has none (17% of records); `jurisdiction` may be a
multi-value string (the ECB's spans 19 country codes) — kept verbatim, not parsed.

### 2. Build script — `scripts/build-topics.mjs`

Run once, output committed. Keeps the vendored file reproducible rather than a mystery
blob. Reads:

- `../gics-topic-tagging/data/results/gics_classifications.json` (same repo)
- `../../../carver-showcase/data/topic_catalog.csv` (sibling repo, **build time only**)

**Subset: ~150 of 1,096 records.** Selection is rule-based and deterministic, chosen to
preserve every property the demo depends on:

| Rule | Count | Why |
|---|---|---|
| Marquee keep-list | ~35 | US SEC, FCA, Fed, ECB, BoE, MAS, BIS, CFTC, FDIC, CFPB, FTC, EPA, ICO, APRA, ASIC, RBA, EBA, BOK/FSS/FSC — recognizable questions must work |
| Full `SEC` + `CBI` + `CMA` families | 15 | The ambiguity demo dies without them |
| "Securities" decoys | ~8 | Preserves the substring-collision trap |
| Multilingual names | ~10 | Korean, Thai, Arabic, Hebrew, Chinese |
| ≥2 per sector × 19 sectors | ~38 | Keeps both taxonomies and full sector spread |
| Confidence mix (incl. low/medium) | — | The agent has something real to report |
| Deterministic stratified fill | remainder | Reach ~150 without hand-picking |

Rules overlap; the script unions them and fills to the target. Expected ~40–60KB.

The ~950 dropped records are long-tail municipal/state bodies that add file size without
adding a demo capability. **The subset is a demo fixture, not a Carver dataset** — the
README must say so, so nobody mistakes it for authoritative coverage.

### 3. Tool — `src/mastra/tools/carver-topic-tool.ts`

`createTool` with Zod schemas, matching the `word-count-tool.ts` pattern it replaces.

Exported as `searchCarverTopics`, with `id: 'search-carver-topics'`. The export name and the
key in the agent's `tools: { ... }` object must match, because **the object key is the name
the model sees** — the earlier trace showed `tool: 'wordCountTool'` (the key) even though
that tool's `id` was `word-count`. The instructions therefore name `searchCarverTopics`.

- **input:** `{ query: string, limit?: number }` (default limit 5)
- **output:** `{ matchCount: number, matches: Array<{ name, acronym, jurisdiction, system, sector, industry, subIndustry, confidence }> }`

**Ranked matching** — the core logic, and what defuses the SEC trap:

1. exact acronym match (case-insensitive)
2. exact name match (case-insensitive)
3. name starts-with
4. name substring

Results are ranked by tier, then returned up to `limit`. `matchCount` reports total matches
found **before** truncation, so the agent can tell the difference between "one answer" and
"five jurisdictions, showing you 5 of 5".

Data loads once at module scope into a module-level array. At ~150 records the file is
small; no index, no cache, no async. A miss returns `{ matchCount: 0, matches: [] }` — not
an error, not a throw.

### 4. Agents — the contrast pair

Both use `model: "openai/gpt-5.6-sol"` and share this base instruction verbatim:

> You are a helpful assistant that answers questions about financial and government
> regulatory bodies — which sector or industry they belong to. Keep responses short.

**`baseline-agent.ts`** — `id: 'baseline-agent'`, `name: 'Baseline Agent (no data)'`. Base
instruction only. No tools. Nothing added, nothing subtracted.

**`carver-agent.ts`** — `id: 'carver-agent'`, `name: 'Carver Agent (grounded)'`. Base
instruction plus `tools: { searchCarverTopics }` and only the rules needed to use it well:

- Use `searchCarverTopics` for any question about a regulatory body; do not answer from
  memory.
- Report the classification **and its confidence**.
- **When matches span multiple jurisdictions, say so and disambiguate — never silently pick
  one.** This is the ambiguity finding encoded as behaviour.
- If `matchCount` is 0, say the body isn't in the dataset — do not guess.

The delta is the tool and its usage rules. Nothing in the baseline's prompt weakens it.

## Data flow — the demo, side by side

Same question, both agents:

```
user: "what sector is the SEC in?"

baselineAgent (no tools)
  → model answers from memory
  → "The SEC is the US securities regulator — Financials."
  → trace: agent_run → model_generation → text          (no tool_call)

carverAgent (tool)
  → searchCarverTopics({ query: "SEC" })
  → tier-1 exact acronym match → 5 records across GH/NG/TH/US/TH
  → { matchCount: 5, matches: [...5, each with jurisdiction...] }
  → "SEC matches 5 bodies. The US SEC is Investment Banking & Brokerage
     (Financials), high confidence. Also Ghana, Nigeria, Thailand ×2."
  → trace: agent_run → model_generation → tool_call(searchCarverTopics) → text
```

The contrast lands on three axes, all visible in Studio:

1. **Jurisdiction blindness** — baseline assumes US; grounded finds five.
2. **Provenance** — grounded cites a record + confidence; baseline cites nothing.
3. **Traceability** — the grounded trace has a `tool_call` span with the exact payload;
   the baseline trace has no retrieval step at all. The empty trace *is* the point.

Demo questions, in order of impact: `SEC` (ambiguity), `금융감독원` (a name the model likely
cannot classify), `FCA` (both may agree — honest, and shows the tool isn't magic).

## Error handling

| Case | Behaviour |
|---|---|
| No match | `{ matchCount: 0, matches: [] }`; agent says not found, does not guess |
| Empty/whitespace query | Zod `.min(1)` rejects; Mastra surfaces the validation error |
| Ambiguous acronym | All matches returned with jurisdictions; agent disambiguates |
| `limit` exceeds matches | Returns what exists; `matchCount` still reports the true total |
| Data file missing/malformed | Throws at startup, not per-request — fails loudly at `mastra dev`, not mid-demo |

## Testing

The matching function is pure over an array — unit-testable with no LLM, no network, no
Mastra runtime. Tests assert against the vendored fixture:

1. `"SEC"` → the 5-body family; `matchCount === 5`; the US SEC is present.
2. `"BOK"` → 한국은행 (acronym hit on a non-Latin name).
3. `"FCA"` → Financial Conduct Authority (the case that fails without the join).
4. `"Securities"` → substring tier; the real SEC does **not** outrank exact-acronym hits.
5. `"zzzznotareal"` → `{ matchCount: 0, matches: [] }`, no throw.
6. `limit` truncates `matches` but not `matchCount`.

No test runner is configured in this project yet (`package.json` has the npm default
`"test": "echo Error: no test specified && exit 1"`). Adding one is part of implementation;
`node --test` is the zero-dependency option and is the recommendation.

## Decisions and trade-offs

- **Vendored copy over runtime cross-project read.** Duplicates data that exists elsewhere
  and can go stale if `gics-topic-tagging` re-runs. Accepted: self-containment matters more
  for a spike, and the build script + this spec record the provenance. Revisit if the
  taxonomy starts changing often.
- **~150 records over all 1,096.** User's call, and it fits the demo. Documented as a
  fixture so nobody reads it as coverage.
- **`wordCountTool` and `helloAgent` deleted.** They were scaffolding to prove the trace
  view worked; `searchCarverTopics` now does that better, on real data. Keeping them would put
  a third, irrelevant agent in a two-agent contrast demo and blur the comparison. Lean wins.
  Reversible — they are in git history on this branch.
- **Two agents over one agent toggled.** A single agent whose tool is switched on and off
  would need a restart between answers and would lose the side-by-side trace comparison.
  Two registered agents let the user click between them in Studio and compare traces
  directly. Cost: a duplicated base instruction string across two files. Accepted at this
  size; extract to a shared constant if it grows.
- **No live API path.** The key is dead (finding 1). The tool interface
  (`query` → `matches`) would not have to change if a live backend were slotted in later.

## Out of scope

Live Carver API access; feed entries and regulatory updates (the actual "intelligence"
product — this is reference data); semantic/vector search; memory; workflows; the
`carver-feeds-skill` Python SDK; any UI.
