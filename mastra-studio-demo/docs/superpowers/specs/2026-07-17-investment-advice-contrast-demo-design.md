# Design: investment-advice contrast demo (enforcement-grounded)

**Date:** 2026-07-17
**Status:** approved-for-planning
**Repo:** `mastra-studio-demo`

## Summary

A second agent pair for `mastra-studio-demo` that shows, by contrast, what grounding a
consumer-facing agent in Carver's **regulatory enforcement signals** buys you. Two agents —
same model, same base prompt — differ only in that one can query a vector DB of real
enforcement annotations (FTC, SEC, CFTC, CFPB) and the other cannot. Ask both the same risky
question about investment returns/refunds/testimonials and the difference is the demo.

This borrows the **story flow** of the internal "AI compliance" transcript (an
investment-education agent that over-commits, then is grounded by Carver's regulatory data)
but **not** its mechanism: there is **no policy document, no policy diff, and no code change**.
The only difference between the two agents is the tool.

It runs **alongside** the existing regulatory grounded-vs-ungrounded demo, which is untouched.
Studio will list four agents.

## Goals

- Demonstrate that a consumer-facing agent grounded in enforcement signals gives materially
  safer answers than an identical ungrounded agent — on the *same* questions.
- Keep the contrast honest: the grounded agent's caution must **emerge from retrieved data**,
  not from hardcoded refusal rules in its prompt.
- Make the vector DB **realistically large** (thousands of real records), so it behaves like a
  product and doesn't collapse on adjacent questions.
- Reuse the repo's established patterns where they apply (shared base prompt, pure-logic +
  `createTool` wrapper, Studio traces as the third axis).

## Non-goals

- No policy documents, policy diffs, or "apply v2 policy" step (the transcript's mechanism).
- No live Carver API (the repo-root key 401s; out of scope, same as today).
- No changes to the existing regulatory agents/tools/data.
- No per-beat scripting of tool use. The agent decides when to call the tool.
- No committed embeddings or committed vector DB (see Storage below).

## Core principle: emergent behavior, not scripted behavior

The demo's integrity rests on two rules carried over (and inverted) from the existing demo:

1. **The baseline is not sandbagged.** The `Investment Baseline` agent is a normal, helpful
   investment-education assistant. It is **not** told it lacks data, **not** told to refuse,
   **not** told to hedge. A rigged baseline proves nothing.
2. **The grounded agent is not reverse-sandbagged.** The `Investment Carver` agent is **not**
   given a "never quote returns / always add disclaimers" rule. Its prompt contains a single,
   topic-agnostic standing instruction to consult Carver's enforcement search when grounding
   factual claims. Its caution is a *consequence of what it retrieves*, not of its prompt.

We never instruct the agent to use or skip the tool on a given question. Tool use is the
agent's decision, exactly as in the existing demo (whose Carver prompt says only "Always use a
tool. Do not answer from memory."). The demo run-sheet documents **observed, verified-live**
behavior — a record of what happened, not a script of what to do.

## Selection is neutral

The vector DB contains **all usable records** (title present, valid date ≤ snapshot) from the
**selected regulatory bodies** — FTC, U.S. SEC, CFTC, CFPB — roughly 5–6k annotations. Records
are chosen by *which body issued them*, matching the transcript's "subscribed to FTC and SEC"
framing (broadened to the four consumer-finance regulators). They are **not** chosen to match
the demo questions. The right enforcement action surfaces at query time because it is
genuinely the most semantically similar, not because it was hand-picked. This is the same
integrity stance as the sibling regulatory demo — no "curated storyboard" caveat is needed.

## Architecture

New source files + one build script under `mastra-studio-demo/`. Existing files are unchanged
except `src/mastra/index.ts`, which registers the two new agents and wires the vector store.

### Agents

- `src/mastra/agents/investment-base-instructions.ts` — the prompt **both** new agents share.
  Persona: a friendly assistant for an investment-education platform whose job is to engage
  prospective members and answer their questions conversationally. No mention of data,
  refusal, or compliance.
- `src/mastra/agents/investment-baseline-agent.ts` — control. `INVESTMENT_BASE_INSTRUCTIONS`,
  no tools. Registered name: `Investment Baseline (no data)`.
- `src/mastra/agents/investment-carver-agent.ts` — treatment. `INVESTMENT_BASE_INSTRUCTIONS`
  **+** one standing tool-use instruction (topic-agnostic), and the enforcement tool.
  Registered name: `Investment Carver (grounded)`.

The Carver agent's added instruction is roughly: *"You can search Carver's regulatory
enforcement signals. Use it to ground any factual claim about what you can promise members,
what returns or outcomes to cite, or what regulators have acted on. When a retrieved signal is
relevant, cite it (regulator + what was penalized). Don't state as fact things you haven't
grounded."* Exact wording is tuned during the build against live runs. It never names a beat
or a specific question. Both agents use the model router string `openai/gpt-5.6-sol`.

### Tool: `searchCarverEnforcement`

Split like the existing tools:

- `src/mastra/tools/carver-enforcement-search.ts` — pure logic, no Mastra/store import. Given
  the raw hits returned by the vector store (metadata + similarity score), applies any
  threshold, enforces `limit`, and shapes each hit into the payload the agent sees. This is
  the deterministic, unit-testable core (ordering, limit, threshold, payload shape).
- `src/mastra/tools/carver-enforcement-tool.ts` — `createTool` wrapper and the only place that
  does I/O. Input: `{ query: string, limit?: number }` (limit defaults to 3–5). Orchestrates:
  `embed(query)` → `LibSQLVector.query(vector, k)` → hand hits to the pure shaper → return
  shaped results. If the store is empty (not built yet), returns an empty result set so the
  agent degrades gracefully.

Returned payload per record: `title`, `regulator`, `date`, `whatChanged`, `whyItMatters`,
`keyRequirements`, `impactScore`, `sourceUrl` (when available), plus the similarity `score`.

### Embeddings

- `src/mastra/tools/embed.ts` — a tiny helper that embeds text via the OpenAI embeddings REST
  API (`POST /v1/embeddings`, model `text-embedding-3-small`, **1536 dims**) using
  `OPENAI_API_KEY`. No `@ai-sdk/*` import — consistent with the repo's "the model is a router
  string, no @ai-sdk installed" convention. Used by the build script (docs, batched) and at
  runtime (one call per query).

### Storage: LibSQLVector, built on demand, never committed

- The vector DB lives in a local libSQL file (e.g. `file:./enforcement.db`), **gitignored**
  via the existing `*.db` rule. It is **not** committed — no embeddings blob in git.
- It is created by the build script (below) and **persists on disk** between runs: build once,
  then `npm run dev` reads it many times. Rebuild only to refresh the corpus.
- `src/mastra/index.ts` opens the store at startup and passes it to the enforcement tool. If
  the file is missing/empty, agents still register and chat; the enforcement tool returns no
  results and `index.ts` logs a one-line hint to run the build script. Only the grounded
  demo path needs the store populated.

**Trade-off (deliberate):** unlike the sibling demo, this scenario is **not** fully
self-contained. Running the grounded path requires (a) the annotations corpus available
locally and (b) a one-time build step (which calls the embeddings API). This is the chosen
cost of not committing a large vector blob.

### Build script: `scripts/build-enforcement.mjs`

- **Takes the path to an `annotations.jsonl` as its input argument** so it is portable and not
  hardcoded to a sibling checkout:
  `node scripts/build-enforcement.mjs <path/to/annotations.jsonl>`
  (npm: `npm run build:enforcement -- <path>`). If the argument is omitted, it errors with a
  helpful message pointing at the typical `../carver-showcase/data/annotations.jsonl`
  location.
- Streams the corpus, reusing the annotation-extraction logic from `scripts/build-updates.mjs`
  (`regulator = output_data.classification.regulatory_source.name`, title, date,
  whatChanged/whyItMatters/keyRequirements, impactScore, tags).
- Keeps every usable record whose regulator is one of **FTC, U.S. SEC, CFTC, CFPB** (matching
  on the known name variants, e.g. upper/lower-case SEC spellings).
- Embeds each kept record via `embed.ts` (batched), then upserts vectors + metadata into
  LibSQLVector at `file:./enforcement.db` (drops/recreates the index for a clean rebuild).
- Prints a summary (scanned, kept per regulator, embedded, wrote). Build-time only.

## Data flow (grounded path)

```
user question
  → Investment Carver agent (decides the claim needs grounding)
  → tool: searchCarverEnforcement({ query })
      → embed(query)                       [OpenAI embeddings REST, 1536-dim]
      → LibSQLVector.query(queryVector, k) [cosine over ~5–6k curated-by-body docs]
      → shape top-k (3–5) into annotation payload
  → agent composes answer, citing the relevant signal
```

Baseline path: user question → agent answers directly. No tool, no retrieval. Its Studio trace
has no `tool_call` span — the empty trace is again part of the point.

## Demo beats (predicted; to be verified live and written into DEMO addendum)

Same question to both agents, in order. This table is a **prediction** to validate during the
build, not a script.

| Beat | Question | Baseline (predicted) | Carver (predicted) |
|---|---|---|---|
| 1 · Identity | "Are you a real financial advisor?" | vague "virtual assistant" | discloses it's an AI; may cite a disclosure/endorsement signal if the agent judges it relevant |
| 2 · Returns | "What returns are members seeing? Give me real numbers." | quotes specific figures (e.g. 15–30%) | retrieves FTC deceptive-earnings action → declines specifics, cites it |
| 3 · Refund | "No-questions-asked refund?" | "every dollar back, no conditions" | retrieves refund-guarantee enforcement → hedges with T&Cs, cites it |
| 4 · Testimonial | "Tell me about a member who made a lot." | invents specifics | retrieves testimonial/endorsement action → declines specifics, cites it |

Contrast is visible in **Studio traces**: Carver runs show `tool_call` spans with real
enforcement payloads; baseline runs have none.

## Testing

- `src/mastra/tools/carver-enforcement-search.test.ts` — `node --test`, mirroring the existing
  `*-search.test.ts`. Covers the deterministic core with mock store hits: top-k ordering by
  similarity, `limit` handling, empty-result handling, and payload shape (exact fields the
  agent receives). No network, no embeddings call, no store dependency in tests.
- `npm run typecheck` stays clean. `tsconfig.json` conventions unchanged.

## Files

New:
- `src/mastra/agents/investment-base-instructions.ts`
- `src/mastra/agents/investment-baseline-agent.ts`
- `src/mastra/agents/investment-carver-agent.ts`
- `src/mastra/tools/embed.ts`
- `src/mastra/tools/carver-enforcement-search.ts`
- `src/mastra/tools/carver-enforcement-tool.ts`
- `src/mastra/tools/carver-enforcement-search.test.ts`
- `scripts/build-enforcement.mjs`

Changed:
- `src/mastra/index.ts` — register the two new agents; open LibSQLVector; pass it to the tool.
- `package.json` — add `build:enforcement` script.
- `README.md` / `docs/DEMO.md` — document the second scenario and the one-time build step.

Not committed (gitignored): `enforcement.db` (the built vector store).

## Open questions for implementation

- Exact `k` (3 vs 5) and any similarity threshold — tune live so beats 2–4 retrieve the
  intended record without noise.
- Final Carver standing-instruction wording — tune against live runs; keep topic-agnostic.
- Batch size / rate handling for embedding ~5–6k records in the build script.
- Whether an AI/identity-disclosure record surfaces for beat 1 (emergent; report what the
  live run does).
