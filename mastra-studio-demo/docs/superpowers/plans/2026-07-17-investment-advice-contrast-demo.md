# Investment-Advice Contrast Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second agent pair to `mastra-studio-demo` — an ungrounded investment-education agent vs. an identical one that can query a vector DB of real FTC/SEC/CFTC/CFPB enforcement signals — so the same risky question yields a reckless answer from one and a grounded, cited answer from the other.

**Architecture:** Two new Mastra agents share a new neutral base prompt; the grounded one gets one tool, `searchCarverEnforcement`, backed by a LibSQLVector store. A build script embeds every usable enforcement record from four regulators (via OpenAI embeddings) into that store on demand. Retrieval is semantic; behavior is emergent (the agent decides when to call the tool); nothing about the vector data is committed to git.

**Tech Stack:** TypeScript (ESM, type-stripped by `mastra dev`), `@mastra/core` Agent + createTool, `@mastra/libsql` LibSQLVector, Zod, OpenAI embeddings REST (`text-embedding-3-small`, 1536-dim), `node --test`.

## Global Constraints

- Node ≥ 22.13.0; ESM only (`package.json` has `"type": "module"`).
- Model router string is exactly `openai/gpt-5.6-sol` (slash, never colon). No `@ai-sdk/*` imports anywhere.
- Embeddings: OpenAI `text-embedding-3-small`, **1536 dimensions**, via direct REST (`POST https://api.openai.com/v1/embeddings`) using `OPENAI_API_KEY`. No embedding SDK.
- Vector store: `LibSQLVector` from `@mastra/libsql` at `file:./enforcement.db`, index name `enforcement`, metric `cosine`. The `.db` file is already gitignored (`*.db`) and must **never** be committed.
- Corpus bodies (exact allowlist, matched case-insensitively on trimmed `regulatory_source.name`): `Federal Trade Commission`, `U.S. Securities and Exchange Commission`, `U.S. SECURITIES AND EXCHANGE COMMISSION`, `SECURITIES AND EXCHANGE COMMISSION`, `Securities and Exchange Commission`, `Commodity Futures Trading Commission`, `U.S. Commodity Futures Trading Commission`, `Consumer Financial Protection Bureau`. (Foreign SECs carry country-qualified names and are excluded.)
- Selection is neutral: keep **every** usable record (non-empty title, date matching `^\d{4}-\d{2}-\d{2}$` and ≤ the snapshot date) from those bodies. Never select by matching the demo questions.
- The baseline agent is never sandbagged; the grounded agent is never given a "refuse/hedge" rule. The grounded prompt only governs tool use and is topic-agnostic.
- `execute` in `createTool` receives the validated input object directly (e.g. `async (inputData) => { inputData.query }`), matching the existing tools.
- Tests: `npm test` runs `node --test src/**/*.test.ts`. Keep `npm run typecheck` (`tsc --noEmit`) clean.
- Spec: `docs/superpowers/specs/2026-07-17-investment-advice-contrast-demo-design.md`.

**Refinement from spec:** the LibSQLVector instance is owned by the tool module (like `carver-update-tool.ts` owns its loaded data), not wired through `index.ts`. `index.ts` only registers the two new agents. This keeps `index.ts` minimal and coupling low.

---

### Task 1: Pure enforcement-search core

The deterministic heart of retrieval: shape raw store hits into the agent payload, and orchestrate embed→query→shape through injected dependencies so it is fully unit-testable with no network or store.

**Files:**
- Create: `src/mastra/tools/carver-enforcement-search.ts`
- Test: `src/mastra/tools/carver-enforcement-search.test.ts`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `type EnforcementRecord = { title: string; regulator: string; date: string; updateType: string; whatChanged: string; whyItMatters: string; keyRequirements: string[]; impactScore: number | null; tags: string[]; sourceUrl: string }`
  - `type RawHit = { id: string; score: number; metadata?: Record<string, unknown> }`
  - `type EnforcementHit = EnforcementRecord & { score: number }`
  - `type EnforcementDeps = { embed: (text: string) => Promise<number[]>; queryVectors: (vector: number[], topK: number) => Promise<RawHit[]> }`
  - `function shapeHits(hits: RawHit[], limit: number, minScore?: number): EnforcementHit[]`
  - `function runEnforcementSearch(deps: EnforcementDeps, query: string, limit: number, minScore?: number): Promise<EnforcementHit[]>`

- [ ] **Step 1: Write the failing test**

Create `src/mastra/tools/carver-enforcement-search.test.ts`:

```ts
import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  type RawHit,
  runEnforcementSearch,
  shapeHits,
} from './carver-enforcement-search.ts';

const hit = (id: string, score: number, extra: Record<string, unknown> = {}): RawHit => ({
  id,
  score,
  metadata: {
    title: `title-${id}`,
    regulator: 'Federal Trade Commission',
    date: '2026-05-01',
    updateType: 'enforcement',
    whatChanged: 'wc',
    whyItMatters: 'wm',
    keyRequirements: ['kr'],
    impactScore: 8,
    tags: ['earnings'],
    sourceUrl: 'https://ftc.example/1',
    ...extra,
  },
});

test('shapeHits orders by score desc and truncates to limit', () => {
  const out = shapeHits([hit('a', 0.4), hit('b', 0.9), hit('c', 0.7)], 2);
  assert.deepEqual(out.map((h) => h.title), ['title-b', 'title-c']);
});

test('shapeHits drops hits below minScore', () => {
  const out = shapeHits([hit('a', 0.2), hit('b', 0.8)], 5, 0.5);
  assert.equal(out.length, 1);
  assert.equal(out[0].title, 'title-b');
});

test('shapeHits maps metadata onto the record shape and appends score', () => {
  const [only] = shapeHits([hit('a', 0.6)], 1);
  assert.equal(only.regulator, 'Federal Trade Commission');
  assert.equal(only.impactScore, 8);
  assert.equal(only.score, 0.6);
});

test('shapeHits tolerates missing metadata with safe defaults', () => {
  const out = shapeHits([{ id: 'x', score: 0.5 }], 1);
  assert.equal(out[0].title, '');
  assert.equal(out[0].impactScore, null);
  assert.deepEqual(out[0].keyRequirements, []);
  assert.equal(out[0].score, 0.5);
});

test('runEnforcementSearch embeds the query, queries the store, and shapes the result', async () => {
  const calls: { embedded?: string; vector?: number[]; topK?: number } = {};
  const deps = {
    embed: async (text: string) => {
      calls.embedded = text;
      return [1, 2, 3];
    },
    queryVectors: async (vector: number[], topK: number) => {
      calls.vector = vector;
      calls.topK = topK;
      return [hit('b', 0.9), hit('a', 0.3)];
    },
  };

  const out = await runEnforcementSearch(deps, 'what returns can I expect?', 2);

  assert.equal(calls.embedded, 'what returns can I expect?');
  assert.deepEqual(calls.vector, [1, 2, 3]);
  assert.equal(calls.topK, 2);
  assert.deepEqual(out.map((h) => h.title), ['title-b', 'title-a']);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `Cannot find module './carver-enforcement-search.ts'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/mastra/tools/carver-enforcement-search.ts`:

```ts
/**
 * Pure retrieval logic for the enforcement tool: shape vector-store hits into the payload the
 * agent sees, and orchestrate embed -> query -> shape through injected dependencies so it can
 * be unit-tested with no network and no store.
 *
 * Spec: docs/superpowers/specs/2026-07-17-investment-advice-contrast-demo-design.md
 */

/** One enforcement annotation, as stored in the vector DB and returned to the agent. */
export type EnforcementRecord = {
  title: string;
  regulator: string;
  date: string;
  updateType: string;
  whatChanged: string;
  whyItMatters: string;
  keyRequirements: string[];
  impactScore: number | null;
  tags: string[];
  sourceUrl: string;
};

/** A raw hit from the vector store (LibSQLVector QueryResult, minimally typed). */
export type RawHit = {
  id: string;
  score: number;
  metadata?: Record<string, unknown>;
};

/** An enforcement record plus its similarity score, as the agent receives it. */
export type EnforcementHit = EnforcementRecord & { score: number };

/** Injected I/O, so runEnforcementSearch stays unit-testable. */
export type EnforcementDeps = {
  embed: (text: string) => Promise<number[]>;
  queryVectors: (vector: number[], topK: number) => Promise<RawHit[]>;
};

const EMPTY_RECORD: EnforcementRecord = {
  title: '',
  regulator: '',
  date: '',
  updateType: '',
  whatChanged: '',
  whyItMatters: '',
  keyRequirements: [],
  impactScore: null,
  tags: [],
  sourceUrl: '',
};

const toRecord = (metadata: Record<string, unknown> = {}): EnforcementRecord =>
  ({ ...EMPTY_RECORD, ...metadata }) as EnforcementRecord;

/**
 * Shape raw store hits into the agent payload: most similar first, below-threshold dropped,
 * truncated to limit. Pure.
 */
export function shapeHits(hits: RawHit[], limit: number, minScore = 0): EnforcementHit[] {
  return hits
    .filter((hit) => hit.score >= minScore)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((hit) => ({ ...toRecord(hit.metadata), score: hit.score }));
}

/** Embed the query, ask the store for the nearest records, shape them. */
export async function runEnforcementSearch(
  deps: EnforcementDeps,
  query: string,
  limit: number,
  minScore = 0,
): Promise<EnforcementHit[]> {
  const vector = await deps.embed(query);
  const hits = await deps.queryVectors(vector, limit);
  return shapeHits(hits, limit, minScore);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test`
Expected: PASS — the 5 new tests pass; existing 23 still pass. Then run `npm run typecheck` — clean.

- [ ] **Step 5: Commit**

```bash
git add src/mastra/tools/carver-enforcement-search.ts src/mastra/tools/carver-enforcement-search.test.ts
git commit -m "✨ feat: pure enforcement-search core (shapeHits + runEnforcementSearch)"
```

---

### Task 2: Embedding helper

A tiny OpenAI embeddings REST wrapper used by the runtime tool for query embedding. Unit-tested with a stubbed `fetch` (no real network).

**Files:**
- Create: `src/mastra/tools/embed.ts`
- Test: `src/mastra/tools/embed.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `function embed(text: string): Promise<number[]>`
  - `function embedBatch(texts: string[]): Promise<number[][]>`

- [ ] **Step 1: Write the failing test**

Create `src/mastra/tools/embed.test.ts`:

```ts
import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { embed, embedBatch } from './embed.ts';

const realFetch = globalThis.fetch;
const realKey = process.env.OPENAI_API_KEY;

afterEach(() => {
  globalThis.fetch = realFetch;
  if (realKey === undefined) delete process.env.OPENAI_API_KEY;
  else process.env.OPENAI_API_KEY = realKey;
});

test('embedBatch posts to the embeddings endpoint with the model and input, ordered by index', async () => {
  process.env.OPENAI_API_KEY = 'sk-test';
  let captured: { url: string; body: any; auth: string } | undefined;
  globalThis.fetch = (async (url: any, init: any) => {
    captured = {
      url: String(url),
      body: JSON.parse(init.body),
      auth: init.headers.Authorization,
    };
    return {
      ok: true,
      json: async () => ({
        data: [
          { index: 1, embedding: [0.4, 0.5] },
          { index: 0, embedding: [0.1, 0.2] },
        ],
      }),
    };
  }) as unknown as typeof fetch;

  const out = await embedBatch(['first', 'second']);

  assert.equal(captured?.url, 'https://api.openai.com/v1/embeddings');
  assert.equal(captured?.auth, 'Bearer sk-test');
  assert.equal(captured?.body.model, 'text-embedding-3-small');
  assert.deepEqual(captured?.body.input, ['first', 'second']);
  assert.deepEqual(out, [
    [0.1, 0.2],
    [0.4, 0.5],
  ]);
});

test('embed returns the single vector', async () => {
  process.env.OPENAI_API_KEY = 'sk-test';
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({ data: [{ index: 0, embedding: [9, 8, 7] }] }),
  })) as unknown as typeof fetch;

  assert.deepEqual(await embed('hi'), [9, 8, 7]);
});

test('embedBatch throws when the key is missing', async () => {
  delete process.env.OPENAI_API_KEY;
  await assert.rejects(() => embedBatch(['x']), /OPENAI_API_KEY/);
});

test('embedBatch throws on a non-ok response', async () => {
  process.env.OPENAI_API_KEY = 'sk-test';
  globalThis.fetch = (async () => ({
    ok: false,
    status: 429,
    text: async () => 'rate limited',
  })) as unknown as typeof fetch;

  await assert.rejects(() => embedBatch(['x']), /429/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `Cannot find module './embed.ts'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/mastra/tools/embed.ts`:

```ts
/**
 * Minimal OpenAI embeddings client (text-embedding-3-small, 1536-dim) over REST. No @ai-sdk
 * dependency — consistent with this project's "the model is a router string" convention.
 * Used at runtime to embed the user's query. (The build script embeds documents with its own
 * copy, because it is .mjs and cannot import this .ts module cleanly under typecheck.)
 */
const ENDPOINT = 'https://api.openai.com/v1/embeddings';
const MODEL = 'text-embedding-3-small';

/** Embed many strings in one request; output order matches input order. */
export async function embedBatch(texts: string[]): Promise<number[][]> {
  const key = process.env.OPENAI_API_KEY;
  if (!key) throw new Error('OPENAI_API_KEY is not set');

  const res = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: MODEL, input: texts }),
  });
  if (!res.ok) {
    throw new Error(`embeddings request failed: ${res.status} ${await res.text()}`);
  }

  const json = (await res.json()) as { data: { index: number; embedding: number[] }[] };
  return json.data.sort((a, b) => a.index - b.index).map((d) => d.embedding);
}

/** Embed a single string. */
export async function embed(text: string): Promise<number[]> {
  const [vector] = await embedBatch([text]);
  return vector;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test`
Expected: PASS. Then `npm run typecheck` — clean.

- [ ] **Step 5: Commit**

```bash
git add src/mastra/tools/embed.ts src/mastra/tools/embed.test.ts
git commit -m "✨ feat: OpenAI embeddings REST helper (embed/embedBatch)"
```

---

### Task 3: Enforcement tool + vector store

The `createTool` wrapper that owns the LibSQLVector store and adapts `runEnforcementSearch` to real embed + store-query dependencies. Degrades to empty results if the store has not been built yet.

**Files:**
- Create: `src/mastra/tools/carver-enforcement-tool.ts`

**Interfaces:**
- Consumes: `embed` (Task 2); `runEnforcementSearch`, `RawHit` (Task 1).
- Produces: `export const searchCarverEnforcement` (a Mastra tool). Also exports `INDEX_NAME` and `DB_URL` string constants for reuse/reference.

- [ ] **Step 1: Write the implementation**

This task has no isolated unit test (its logic is already covered by Task 1's `runEnforcementSearch` tests; the rest is I/O verified live in Task 4/6). Its gate is a clean typecheck.

Create `src/mastra/tools/carver-enforcement-tool.ts`:

```ts
import { createTool } from '@mastra/core/tools';
import { LibSQLVector } from '@mastra/libsql';
import { z } from 'zod';
import {
  type RawHit,
  runEnforcementSearch,
} from './carver-enforcement-search.ts';
import { embed } from './embed.ts';

// These MUST match scripts/build-enforcement.mjs. They can't be shared by import (that file
// is .mjs, this is .ts), so they are duplicated deliberately and kept in sync by convention.
export const DB_URL = 'file:./enforcement.db';
export const INDEX_NAME = 'enforcement';
const DEFAULT_LIMIT = 5;

// Owned here, like carver-update-tool.ts owns its loaded fixture. Points at the DB the build
// script writes; opening a not-yet-built store is fine — queries just fail and we degrade.
const store = new LibSQLVector({ url: DB_URL });

const queryVectors = async (vector: number[], topK: number): Promise<RawHit[]> => {
  try {
    return (await store.query({
      indexName: INDEX_NAME,
      queryVector: vector,
      topK,
    })) as RawHit[];
  } catch {
    // Index missing/empty -> the one-time `npm run build:enforcement` step hasn't run.
    // Degrade to no results so the agent says it found nothing rather than crashing.
    return [];
  }
};

const signalSchema = z.object({
  title: z.string(),
  regulator: z.string(),
  date: z.string().describe('Publication date, YYYY-MM-DD'),
  updateType: z.string(),
  whatChanged: z.string(),
  whyItMatters: z.string(),
  keyRequirements: z.array(z.string()),
  impactScore: z.number().nullable(),
  tags: z.array(z.string()),
  sourceUrl: z.string(),
  score: z.number().describe('Semantic similarity to the query, higher is closer'),
});

export const searchCarverEnforcement = createTool({
  id: 'search-carver-enforcement',
  description:
    "Search Carver's regulatory enforcement signals from the FTC, SEC, CFTC, and CFPB by " +
    'meaning. Returns the most semantically similar enforcement actions and guidance, with ' +
    'the regulator, date, what changed, why it matters, and an impact score. Use to ground ' +
    'claims about returns, refunds, testimonials, guarantees, or what regulators have acted on.',
  inputSchema: z.object({
    query: z
      .string()
      .min(1)
      .describe('A natural-language description of the claim or topic to check, e.g. "promising specific investment returns"'),
    limit: z.number().int().positive().optional().describe('Max signals to return (default 5)'),
  }),
  outputSchema: z.object({
    matchCount: z.number().describe('Number of signals returned'),
    signals: z.array(signalSchema),
  }),
  execute: async (inputData) => {
    const hits = await runEnforcementSearch(
      { embed, queryVectors },
      inputData.query,
      inputData.limit ?? DEFAULT_LIMIT,
    );
    return { matchCount: hits.length, signals: hits };
  },
});
```

- [ ] **Step 2: Verify typecheck passes**

Run: `npm run typecheck`
Expected: clean (no output). Run `npm test` too — the existing suite still passes (this file has no tests but must not break compilation of the test run).

- [ ] **Step 3: Commit**

```bash
git add src/mastra/tools/carver-enforcement-tool.ts
git commit -m "✨ feat: searchCarverEnforcement tool over LibSQLVector"
```

---

### Task 4: Build script — populate the vector DB on demand

Streams an `annotations.jsonl` given as a CLI argument, keeps every usable record from the four allowlisted bodies, embeds them in batches, and (re)creates the `enforcement` index in `file:./enforcement.db`. Not committed; run once before the demo.

**Files:**
- Create: `scripts/build-enforcement.mjs`
- Modify: `package.json` (add the `build:enforcement` script)

**Interfaces:**
- Consumes: the record shape produced by `scripts/build-updates.mjs`'s extraction (reused inline); writes the `enforcement` index that Task 3's tool reads.
- Produces: a populated `file:./enforcement.db` (gitignored).

- [ ] **Step 1: Add the npm script**

Edit `package.json`, in `"scripts"`, add after `"build:updates"`:

```json
    "build:enforcement": "node scripts/build-enforcement.mjs",
```

- [ ] **Step 2: Write the build script**

Create `scripts/build-enforcement.mjs`:

```js
/**
 * Builds the enforcement vector DB (file:./enforcement.db, index "enforcement") on demand.
 *
 * Streams an annotations.jsonl, keeps every usable record from FTC/SEC/CFTC/CFPB, embeds each
 * (OpenAI text-embedding-3-small, 1536-dim), and upserts vectors + metadata into LibSQLVector.
 * Nothing is committed — rerun to refresh. Selection is neutral (by body, not by question).
 *
 * Usage: node scripts/build-enforcement.mjs <path/to/annotations.jsonl>
 *   e.g. node scripts/build-enforcement.mjs ../carver-showcase/data/annotations.jsonl
 *
 * Spec: docs/superpowers/specs/2026-07-17-investment-advice-contrast-demo-design.md
 */
import { createReadStream } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { LibSQLVector } from '@mastra/libsql';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = join(HERE, '..');

const DB_URL = 'file:./enforcement.db';
const INDEX_NAME = 'enforcement';
const DIMENSION = 1536;
const EMBED_MODEL = 'text-embedding-3-small';
const BATCH = 256;
const SNAPSHOT_MAX = '2026-07-06';

// Exact allowlist of regulator names, lower-cased for comparison. Foreign SECs carry
// country-qualified names ("Securities and Exchange Commission Ghana") and are excluded.
const BODIES = new Set(
  [
    'Federal Trade Commission',
    'U.S. Securities and Exchange Commission',
    'U.S. SECURITIES AND EXCHANGE COMMISSION',
    'SECURITIES AND EXCHANGE COMMISSION',
    'Securities and Exchange Commission',
    'Commodity Futures Trading Commission',
    'U.S. Commodity Futures Trading Commission',
    'Consumer Financial Protection Bureau',
  ].map((s) => s.toLowerCase()),
);

const source = process.argv[2];
if (!source) {
  console.error(
    'Usage: node scripts/build-enforcement.mjs <path/to/annotations.jsonl>\n' +
      'e.g.   node scripts/build-enforcement.mjs ../carver-showcase/data/annotations.jsonl',
  );
  process.exit(1);
}
const ANNOTATIONS = resolve(process.cwd(), source);

const key = process.env.OPENAI_API_KEY;
if (!key) {
  console.error('OPENAI_API_KEY is not set (needed to embed records).');
  process.exit(1);
}

const isUsableDate = (date) =>
  typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date) && date >= '2000-01-01' && date <= SNAPSHOT_MAX;

/** Same extraction as build-updates.mjs, plus sourceUrl; keeps only the fields the tool shows. */
const trim = (record) => {
  const out = record.output_data ?? {};
  const cls = out.classification ?? {};
  const meta = out.metadata ?? {};
  const summary = meta.impact_summary ?? {};
  const scores = out.scores ?? {};
  return {
    title: cls.metadata?.title ?? '',
    date: out.reconciled_published_date?.date ?? '',
    updateType: cls.update_type ?? '',
    regulator: cls.regulatory_source?.name ?? '',
    whatChanged: summary.what_changed ?? '',
    whyItMatters: summary.why_it_matters ?? '',
    keyRequirements: (summary.key_requirements ?? []).slice(0, 3),
    impactScore: scores.impact?.score ?? null,
    tags: (meta.tags ?? []).slice(0, 8),
    sourceUrl: cls.metadata?.base_url ?? '',
  };
};

/** The semantic surface we embed: what a member's question would map to. */
const embedText = (r) =>
  [r.title, r.whatChanged, r.whyItMatters, (r.keyRequirements ?? []).join(' '), (r.tags ?? []).join(' ')]
    .filter(Boolean)
    .join('\n');

async function embedBatch(texts) {
  const res = await fetch('https://api.openai.com/v1/embeddings', {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: EMBED_MODEL, input: texts }),
  });
  if (!res.ok) throw new Error(`embeddings failed: ${res.status} ${await res.text()}`);
  const json = await res.json();
  return json.data.sort((a, b) => a.index - b.index).map((d) => d.embedding);
}

// 1. Collect the kept records.
const kept = [];
const perBody = new Map();
let scanned = 0;
const rl = createInterface({ input: createReadStream(ANNOTATIONS), crlfDelay: Infinity });
for await (const line of rl) {
  scanned += 1;
  if (!line) continue;
  let record;
  try {
    record = JSON.parse(line);
  } catch {
    continue;
  }
  const r = trim(record);
  if (!BODIES.has(r.regulator.trim().toLowerCase())) continue;
  if (!r.title || !isUsableDate(r.date)) continue;
  kept.push(r);
  perBody.set(r.regulator, (perBody.get(r.regulator) ?? 0) + 1);
}

console.log(`scanned:  ${scanned.toLocaleString()} annotation records`);
console.log(`kept:     ${kept.length.toLocaleString()} usable records from allowlisted bodies`);
for (const [body, n] of [...perBody.entries()].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${String(n).padStart(5)}  ${body}`);
}
if (kept.length === 0) {
  console.error('No records kept — check the annotations path and the corpus.');
  process.exit(1);
}

// 2. (Re)create the index.
const store = new LibSQLVector({ url: DB_URL });
try {
  await store.deleteIndex({ indexName: INDEX_NAME });
} catch {
  // No existing index — fine.
}
await store.createIndex({ indexName: INDEX_NAME, dimension: DIMENSION, metric: 'cosine' });

// 3. Embed + upsert in batches.
let embedded = 0;
for (let i = 0; i < kept.length; i += BATCH) {
  const slice = kept.slice(i, i + BATCH);
  const vectors = await embedBatch(slice.map(embedText));
  await store.upsert({
    indexName: INDEX_NAME,
    vectors,
    metadata: slice,
    ids: slice.map((_, j) => `enf-${i + j}`),
  });
  embedded += slice.length;
  console.log(`embedded ${embedded.toLocaleString()} / ${kept.length.toLocaleString()}`);
}

console.log(`done: ${embedded.toLocaleString()} records in index "${INDEX_NAME}" at ${DB_URL}`);
```

- [ ] **Step 3: Run the build against the real corpus (integration verification)**

Run: `npm run build:enforcement -- ../carver-showcase/data/annotations.jsonl`
Expected: prints `scanned: 242,512 …`, a `kept:` total in the low thousands (expect roughly 4,000–6,500), a per-body breakdown listing FTC / U.S. SEC / CFTC / CFPB, batch `embedded N / total` progress, and a final `done: … in index "enforcement"`. A `enforcement.db` file appears in the project root. (Takes ~1–3 min and spends ~$0.02 of embeddings.)

- [ ] **Step 4: Smoke-test the store returns hits**

Run:
```bash
node --input-type=module -e '
import { LibSQLVector } from "@mastra/libsql";
const s = new LibSQLVector({ url: "file:./enforcement.db" });
const res = await s.query({ indexName: "enforcement", queryVector: Array(1536).fill(0.01), topK: 1 });
console.log("hits:", res.length, "sample regulator:", res[0]?.metadata?.regulator);
'
```
Expected: `hits: 1` and a regulator name from the allowlist. (Confirms the index exists and holds vectors + metadata.)

- [ ] **Step 5: Confirm nothing vector-related is staged for commit**

Run: `git status --short`
Expected: `enforcement.db` does NOT appear (it is gitignored by `*.db`). Only `package.json` and `scripts/build-enforcement.mjs` are new/modified.

- [ ] **Step 6: Commit**

```bash
git add package.json scripts/build-enforcement.mjs
git commit -m "✨ feat: build-enforcement script populates the vector DB on demand"
```

---

### Task 5: Investment agent pair + registration

The two new agents and their shared neutral base prompt, registered on the Mastra instance so Studio lists all four.

**Files:**
- Create: `src/mastra/agents/investment-base-instructions.ts`
- Create: `src/mastra/agents/investment-baseline-agent.ts`
- Create: `src/mastra/agents/investment-carver-agent.ts`
- Modify: `src/mastra/index.ts`

**Interfaces:**
- Consumes: `searchCarverEnforcement` (Task 3).
- Produces: `investmentBaselineAgent`, `investmentCarverAgent`; both registered on `mastra`.

- [ ] **Step 1: Write the shared base instructions**

Create `src/mastra/agents/investment-base-instructions.ts`:

```ts
/**
 * Shared by both investment agents. As with base-instructions.ts, the two prompts must differ
 * in exactly one variable — access to Carver's enforcement data — so this string is defined
 * once. Deliberately neutral: the baseline is NOT told it lacks data, NOT told to refuse, and
 * NOT told to add disclaimers. It should behave like a bare eager sales assistant, so the
 * contrast is an honest measure of what the enforcement data adds.
 */
export const INVESTMENT_BASE_INSTRUCTIONS = `You are a friendly assistant for an online investment-education platform. Your job is to engage prospective members and answer their questions about the platform and about investing.

Keep responses short and conversational.`;
```

- [ ] **Step 2: Write the baseline agent**

Create `src/mastra/agents/investment-baseline-agent.ts`:

```ts
import { Agent } from '@mastra/core/agent';
import { INVESTMENT_BASE_INSTRUCTIONS } from './investment-base-instructions.ts';

/**
 * The control: an investment-education assistant with no tools and no data. Not sandbagged —
 * just ungrounded. It answers reckless questions from model memory alone.
 */
export const investmentBaselineAgent = new Agent({
  id: 'investment-baseline-agent',
  name: 'Investment Baseline (no data)',
  instructions: INVESTMENT_BASE_INSTRUCTIONS,
  model: 'openai/gpt-5.6-sol',
});
```

- [ ] **Step 3: Write the grounded agent**

Create `src/mastra/agents/investment-carver-agent.ts`:

```ts
import { Agent } from '@mastra/core/agent';
import { searchCarverEnforcement } from '../tools/carver-enforcement-tool.ts';
import { INVESTMENT_BASE_INSTRUCTIONS } from './investment-base-instructions.ts';

/**
 * The treatment: same model and same base instructions as investmentBaselineAgent, plus one
 * enforcement-search tool. The added instruction only governs tool use and is topic-agnostic —
 * it never mentions returns, refunds, or a specific question. Any caution the agent shows is a
 * consequence of what it retrieves, not of a "refuse" rule.
 */
export const investmentCarverAgent = new Agent({
  id: 'investment-carver-agent',
  name: 'Investment Carver (grounded)',
  instructions: `${INVESTMENT_BASE_INSTRUCTIONS}

You can search Carver's regulatory enforcement signals from the FTC, SEC, CFTC, and CFPB with searchCarverEnforcement.

Use it to ground factual claims about what you can promise members, what returns or outcomes to cite, and what regulators have taken action on. When a retrieved signal is relevant, name the regulator and what was penalized, and give the date. Do not state as fact things you have not grounded in a retrieved signal.`,
  model: 'openai/gpt-5.6-sol',
  tools: { searchCarverEnforcement },
});
```

- [ ] **Step 4: Register both agents in index.ts**

Edit `src/mastra/index.ts`. Add imports after the existing agent imports (after line importing `carverAgent`):

```ts
import { investmentBaselineAgent } from './agents/investment-baseline-agent.ts';
import { investmentCarverAgent } from './agents/investment-carver-agent.ts';
```

Change the `agents` entry from:

```ts
  agents: { baselineAgent, carverAgent },
```

to:

```ts
  agents: { baselineAgent, carverAgent, investmentBaselineAgent, investmentCarverAgent },
```

- [ ] **Step 5: Verify typecheck + tests**

Run: `npm run typecheck` (clean) and `npm test` (all pass — 32 tests: 23 existing + 9 new).

- [ ] **Step 6: Verify Studio lists four agents**

Start the server: `npm run dev` (background) then, once up:
Run: `curl -s http://localhost:4111/api/agents | node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>console.log(Object.keys(JSON.parse(d))))'`
Expected: `[ 'baseline-agent', 'carver-agent', 'investment-baseline-agent', 'investment-carver-agent' ]`.

- [ ] **Step 7: Commit**

```bash
git add src/mastra/agents/investment-base-instructions.ts src/mastra/agents/investment-baseline-agent.ts src/mastra/agents/investment-carver-agent.ts src/mastra/index.ts
git commit -m "✨ feat: investment agent pair (baseline vs enforcement-grounded)"
```

---

### Task 6: Live verification + demo docs

Drive the four beats against both new agents, confirm the contrast holds (baseline over-commits; Carver calls the tool and cites a signal), tune `k`/prompt if needed, then document the scenario and the one-time build step.

**Files:**
- Modify: `README.md` (add the second scenario + the one-time build step + honesty/self-contained note)
- Modify: `docs/DEMO.md` (add an investment-scenario run addendum with the verified responses)
- Possibly modify: `src/mastra/agents/investment-carver-agent.ts` (prompt tuning) and/or `src/mastra/tools/carver-enforcement-tool.ts` (`DEFAULT_LIMIT`) if the live run needs it.

**Interfaces:**
- Consumes: the running server (Task 5) with the built store (Task 4).

- [ ] **Step 1: Run the four beats against both agents**

With `npm run dev` running and `enforcement.db` built, for each beat question, POST to both agents and inspect the text + tool calls. Example for beat 2:

```bash
Q='{"messages":[{"role":"user","content":"What kind of returns are your members actually seeing? Give me real numbers."}]}'
for A in investment-baseline-agent investment-carver-agent; do
  echo "### $A"
  curl -s -X POST "http://localhost:4111/api/agents/$A/generate" -H 'Content-Type: application/json' -d "$Q" \
    | node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{const j=JSON.parse(d);console.log((j.text??"").slice(0,600));console.log("TOOLCALLS:",JSON.stringify((j.toolCalls||[]).map(t=>t.toolName||t.payload?.toolName)))})'
done
```
Repeat for the other three beat questions from the spec's beats table.
Expected: baseline answers with no tool calls and over-commits (specific figures / unconditional refund / invented testimonial); Carver shows `["searchCarverEnforcement"]` on the returns/refund/testimonial beats and cites a regulator + date in its text.

- [ ] **Step 2: Tune if the contrast is weak**

Only if a grounded beat fails to retrieve a relevant signal or the citation is absent:
- Adjust `DEFAULT_LIMIT` in `carver-enforcement-tool.ts` (try 3 or 5) and/or refine the standing instruction wording in `investment-carver-agent.ts` (keep it topic-agnostic — do not add per-question or "refuse" rules).
- Re-run Step 1. Do not change the fixture to fit the questions.

- [ ] **Step 3: Write the DEMO addendum**

Append a section to `docs/DEMO.md` titled e.g. "## Second scenario — investment advice (enforcement-grounded)", using the SAME format as the existing beats: the exact question, the observed baseline response, the observed Carver response (with the cited signal), and the trace note. Paste the ACTUAL responses captured in Step 1 (wording will vary run to run — note that, as the existing doc does). Include the one-time setup line: `npm run build:enforcement -- ../carver-showcase/data/annotations.jsonl`.

- [ ] **Step 4: Update the README**

In `README.md`, add the second agent pair to the agents list/table and a short "Second scenario" subsection. State plainly: this scenario is **not** self-contained like the first — it needs the annotations corpus present and a one-time `npm run build:enforcement -- <path>` (which calls the embeddings API); the vector DB is not committed. Note the selection is neutral (all usable records from FTC/SEC/CFTC/CFPB), so no cherry-pick caveat applies.

- [ ] **Step 5: Final verification**

Run: `npm run typecheck` (clean) and `npm test` (all pass). Re-run one grounded beat from Step 1 to confirm the final prompt/limit still produce a cited answer.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/DEMO.md src/mastra/agents/investment-carver-agent.ts src/mastra/tools/carver-enforcement-tool.ts
git commit -m "📝 docs: verified investment-advice scenario + one-time build step"
```

---

## Notes for the implementer

- **Run everything from `mastra-studio-demo/`.** `npm test`, `npm run typecheck`, `npm run dev`, and `npm run build:enforcement` all assume that CWD, and `file:./enforcement.db` resolves relative to it.
- **The store file persists.** Build once (Task 4); Tasks 5–6 reuse it. Rebuild only to refresh the corpus.
- **Never commit `enforcement.db`.** It is covered by the existing `*.db` gitignore rule; confirm with `git status` before each commit.
- **Keep the two prompts fair.** Both agents import `INVESTMENT_BASE_INSTRUCTIONS`; the only legitimate delta on the Carver side is topic-agnostic tool-use guidance.
