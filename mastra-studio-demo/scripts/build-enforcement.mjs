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
import { createClient } from '@libsql/client';
import { LibSQLVector } from '@mastra/libsql';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = join(HERE, '..');

// `mastra dev` runs the bundled server with its CWD set to src/mastra/public (that is where
// its own mastra.db lands). The tool opens `file:./enforcement.db`, which therefore resolves
// to src/mastra/public/enforcement.db at runtime. Build the DB into that exact location —
// anchored to the project, not to wherever `npm run build:enforcement` was invoked — so the
// running server reads the corpus we just built instead of an empty stub. Keep this path in
// sync with DB_URL in src/mastra/tools/carver-enforcement-tool.ts.
const DB_PATH = join(PROJECT, 'src', 'mastra', 'public', 'enforcement.db');
const DB_URL = `file:${DB_PATH}`;
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

// 2. (Re)create the table, then drop the DiskANN vector index.
//
// The tool queries LibSQLVector WITHOUT a filter, which uses brute-force vector_distance_cos
// over the table — it does NOT need the DiskANN index. That index costs ~320 KB per vector
// (≈2 GB for this corpus); dropping it before we insert keeps the DB ~20 MB. Exact
// brute-force over a few thousand vectors is instant, so nothing is lost.
const store = new LibSQLVector({ id: 'carver-enforcement-vector', url: DB_URL });
try {
  await store.deleteIndex({ indexName: INDEX_NAME });
} catch {
  // No existing index — fine.
}
await store.createIndex({ indexName: INDEX_NAME, dimension: DIMENSION, metric: 'cosine' });
const raw = createClient({ url: DB_URL });
await raw.execute(`DROP INDEX IF EXISTS ${INDEX_NAME}_vector_idx`);

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
