/**
 * Build a vector index from a HAND-CURATED records file (not the annotations crawler).
 *
 *   npm run build:curated -- <domain-id> <path/to/records.json>
 *
 * Used for small, reviewed record sets that do not exist in the carver-showcase corpus —
 * e.g. the state-lending obligations (federal + Colorado + California). The records file is
 * { "records": [ { title, date, regulator, jurisdiction, whatChanged, whyItMatters,
 * keyRequirements, impactScore, tags, sourceUrl }, ... ] }, already in the trimmed shape the
 * tool factory reads. Every record must be grounded in its sourceUrl and REVIEWED before use.
 *
 * Same embed model, dimension, cosine metric, and DiskANN-drop as build-domain-index.mjs, so
 * the resulting DB is byte-compatible with the same tool factory.
 */
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { LibSQLVector } from '@mastra/libsql';
import { createClient } from '@libsql/client';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = join(HERE, '..');
const REGISTRY = join(PROJECT, 'data', 'carver-domains.json');
const DIMENSION = 1536;
const EMBED_MODEL = 'text-embedding-3-small';

const [domainId, source] = process.argv.slice(2);
if (!domainId || !source) {
  console.error('Usage: node scripts/build-curated-index.mjs <domain-id> <path/to/records.json>');
  process.exit(1);
}
const registry = JSON.parse(readFileSync(REGISTRY, 'utf8')).domains;
const domain = registry.find((d) => d.id === domainId);
if (!domain) {
  console.error(`Unknown domain "${domainId}". Known: ${registry.map((d) => d.id).join(', ')}`);
  process.exit(1);
}

const key = process.env.OPENAI_API_KEY;
if (!key) { console.error('OPENAI_API_KEY is not set (needed to embed records).'); process.exit(1); }

const records = JSON.parse(readFileSync(resolve(process.cwd(), source), 'utf8')).records;
if (!Array.isArray(records) || records.length === 0) {
  console.error('No records found in file.'); process.exit(1);
}

const embedText = (r) =>
  [r.title, r.whatChanged, r.whyItMatters, (r.keyRequirements ?? []).join(' '), (r.tags ?? []).join(' ')]
    .filter(Boolean).join('\n');

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

const DB_PATH = join(PROJECT, 'src', 'mastra', 'public', domain.dbFile);
const DB_URL = `file:${DB_PATH}`;

const store = new LibSQLVector({ id: `carver-${domain.id}-vector`, url: DB_URL });
await store.createIndex({ indexName: domain.indexName, dimension: DIMENSION, metric: 'cosine' });
const rawClient = createClient({ url: DB_URL });
await rawClient.execute(`DROP INDEX IF EXISTS ${domain.indexName}_vector_idx`);

const vectors = await embedBatch(records.map(embedText));
await store.upsert({ indexName: domain.indexName, vectors, metadata: records });

const count = await rawClient.execute(`SELECT COUNT(*) AS n FROM ${domain.indexName}`);
console.log(`done: ${Number(count.rows[0].n)} curated records in index "${domain.indexName}" at ${DB_URL}`);
console.log('RESTART `npm run dev` so the agent picks up the new index.');
