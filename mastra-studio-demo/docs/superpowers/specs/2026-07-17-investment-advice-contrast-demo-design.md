# Design: investment-advice contrast demo (enforcement-grounded)

**Date:** 2026-07-17
**Status:** approved-for-planning
**Repo:** `mastra-studio-demo`

## Summary

A second agent pair for `mastra-studio-demo` that shows, by contrast, what grounding a
consumer-facing agent in Carver's **regulatory enforcement signals** buys you. Two agents —
same model, same base prompt — differ only in that one can query a vector DB of curated
FTC/SEC enforcement annotations and the other cannot. Ask both the same risky question about
investment returns/refunds/testimonials and the difference is the demo.

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
- Reuse the repo's established patterns (shared base prompt, pure-logic + `createTool`
  wrapper, committed build-time fixtures, Studio traces as the third axis).

## Non-goals

- No policy documents, policy diffs, or "apply v2 policy" step (the transcript's mechanism).
- No live Carver API (the repo-root key 401s; out of scope, same as today).
- No changes to the existing regulatory agents/tools/data.
- No per-beat scripting of tool use. The agent decides when to call the tool.

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

The only lever the authors control is **what is in the curated dataset**.

## Architecture

Four new source files + one build script + one committed fixture, all under
`mastra-studio-demo/`. The existing files are unchanged except `src/mastra/index.ts`, which
registers the two new agents and initializes the vector store.

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
or a specific question.

Both agents use the same model router string as the existing agents (`openai/gpt-5.6-sol`).

### Tool: `searchCarverEnforcement`

Split like the existing tools:

- `src/mastra/tools/carver-enforcement-search.ts` — pure logic, no Mastra/store import. Given
  the raw hits returned by the vector store (metadata + similarity score), applies any
  threshold, enforces `limit`, and shapes each hit into the payload the agent sees. This is
  the deterministic, unit-testable core (ordering, limit, threshold, payload shape).
- `src/mastra/tools/carver-enforcement-tool.ts` — `createTool` wrapper and the only place that
  does I/O. Input: `{ query: string, limit?: number }`. Orchestrates: `embed(query)` →
  `LibSQLVector.query(vector, k)` → hand the hits to the pure shaper → return shaped results.

Returned payload per record (subset of the annotation shape already used by
`carver-updates.json`): `title`, `regulator`, `date`, `whatChanged`, `whyItMatters`,
`keyRequirements`, `impactScore`, `sourceUrl`, plus the similarity `score`.

### Embeddings

- `src/mastra/tools/embed.ts` — a tiny helper that embeds text via the OpenAI embeddings REST
  API (`POST /v1/embeddings`, model `text-embedding-3-small`, 1536 dims) using
  `OPENAI_API_KEY`. Used at **both** build time (docs) and runtime (query). No `@ai-sdk/*`
  import — consistent with the repo's "the model is a router string, no @ai-sdk installed"
  convention. One embeddings call per tool invocation at runtime.

### Vector store: LibSQLVector

- Initialized in `src/mastra/index.ts` using `LibSQLVector` from `@mastra/libsql` (already a
  dependency). On startup: create the index (dimension 1536) if absent, then **upsert the
  vectors from the committed fixture** (`data/carver-enforcement.json`, which stores each
  record *with* its precomputed embedding). Docs are never re-embedded at runtime.
- Store location: a local libSQL file (gitignored, like `mastra.db`) or `:memory:` seeded at
  startup. Either way the source of truth is the committed JSON fixture, so the demo runs
  offline without `carver-showcase` present — same guarantee as the existing fixtures.

### Data: `data/carver-enforcement.json` (committed)

~12–15 curated enforcement annotations. Each entry: the annotation fields above **plus** its
`embedding` (1536 floats). Committed so the demo is self-contained and rebuilds are stable.

### Build script: `scripts/build-enforcement.mjs` (`npm run build:enforcement`)

- Reads `../carver-showcase/data/annotations.jsonl` (the full 242,512-record corpus).
- Reuses the annotation-extraction logic already in `scripts/build-updates.mjs` (parsing
  `input_data`/`output_data`).
- Filters to **selected bodies** (Federal Trade Commission, U.S. Securities and Exchange
  Commission) intersected with **consumer-investment themes**: deceptive earnings, refund
  guarantees, testimonials/endorsements, misleading claims, unsubstantiated performance, and
  (if a strong match exists) AI/identity disclosure.
- Selects ~12–15 records covering the four demo beats, embeds each via `embed.ts`, writes
  `data/carver-enforcement.json`.
- Build-time only; not needed to run the demo.

## Data flow (grounded path)

```
user question
  → Investment Carver agent (decides the claim needs grounding)
  → tool: searchCarverEnforcement({ query })
      → embed(query)                       [OpenAI embeddings REST]
      → LibSQLVector.query(queryVector, k) [cosine over curated docs]
      → shape top-k into annotation payload
  → agent composes answer, citing the relevant signal
```

Baseline path: user question → agent answers directly. No tool, no retrieval. Its Studio trace
has no `tool_call` span — the empty trace is again part of the point.

## Demo beats (predicted; to be verified live and written into DEMO addendum)

Same question to both agents, in order. This table is a **prediction** to validate during the
build, not a script.

| Beat | Question | Baseline (predicted) | Carver (predicted) |
|---|---|---|---|
| 1 · Identity | "Are you a real financial advisor?" | vague "virtual assistant" | discloses it's an AI; may cite disclosure/endorsement signal if the agent judges it relevant |
| 2 · Returns | "What returns are members seeing? Give me real numbers." | quotes specific figures (e.g. 15–30%) | retrieves FTC deceptive-earnings action → declines specifics, cites it |
| 3 · Refund | "No-questions-asked refund?" | "every dollar back, no conditions" | retrieves refund-guarantee enforcement → hedges with T&Cs, cites it |
| 4 · Testimonial | "Tell me about a member who made a lot." | invents specifics | retrieves testimonial/endorsement action → declines specifics, cites it |

Contrast is visible in **Studio traces**: Carver runs show `tool_call` spans with real
enforcement payloads; baseline runs have none.

## Testing

- `src/mastra/tools/carver-enforcement-search.test.ts` — `node --test`, mirroring the existing
  `*-search.test.ts`. Covers the deterministic core with fixed vectors / mock store hits:
  top-k ordering by similarity, `limit` handling, empty-result handling, and payload shape
  (exact fields the agent receives). No network, no embeddings call in tests.
- `npm run typecheck` stays clean. `tsconfig.json` conventions unchanged.

## Honesty note (documented in the demo README)

The existing regulatory demo makes a point of **neutral fixture selection** (most-recent-per-
topic, deliberately *not* chosen to fit the questions). This investment demo does the
opposite on purpose: its fixture is **curated to a scripted narrative**. Both stances are
legitimate for their respective purposes, but they are opposite, so the investment demo will
be documented explicitly as an **illustrative storyboard** — the records are cherry-picked to
tell a story — to avoid quietly contradicting the sibling demo's integrity claim. What is
*not* cherry-picked: the records are real Carver annotations from the corpus, not fabricated.

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
- `data/carver-enforcement.json` (committed fixture, with embeddings)

Changed:
- `src/mastra/index.ts` — register the two new agents; init + seed LibSQLVector.
- `package.json` — add `build:enforcement` script.
- `README.md` / `docs/DEMO.md` — document the second scenario and the storyboard honesty note.

## Open questions for implementation

- Exact `k` and any similarity threshold (tune live so beats 2–4 retrieve the intended record
  without noise).
- Whether the AI/identity-disclosure record makes the final cut (depends on corpus match
  quality; report during the build).
- Final Carver standing-instruction wording (tune against live runs; keep topic-agnostic).
