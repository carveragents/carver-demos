/**
 * Build a domain vector index from the annotations corpus.
 *
 *   npm run build:domain -- <domain-id> <path/to/annotations.jsonl>
 *
 * Domains are declared in data/carver-domains.json — that file is the single source of
 * truth, shared with src/mastra/tools/carver-domain-tool.ts, so the index name and DB
 * path cannot drift between the builder and the reader.
 *
 * Generalised from the original build-enforcement.mjs, which hardcoded one regulator
 * allowlist and one output path. `npm run build:enforcement` still works and is now a
 * thin alias for `build:domain -- enforcement`; it produces a byte-identical selection.
 *
 * Writes src/mastra/public/<dbFile> — the directory `mastra dev` runs from, so the live
 * agent reads exactly what you built. RESTART `npm run dev` after building.
 *
 * Costs money: embeds every kept record with text-embedding-3-small.
 */
import { createReadStream } from 'node:fs';
import { readFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { LibSQLVector } from '@mastra/libsql';
import { createClient } from '@libsql/client';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = join(HERE, '..');
const REGISTRY = join(PROJECT, 'data', 'carver-domains.json');

const DIMENSION = 1536;
const EMBED_MODEL = 'text-embedding-3-small';
const BATCH = 256;
const SNAPSHOT_MAX = '2026-07-06';

const argv = process.argv.slice(2);
const DRY_RUN = argv.includes('--dry-run');
const [domainId, source] = argv.filter((a) => a !== '--dry-run');
const registry = JSON.parse(readFileSync(REGISTRY, 'utf8')).domains;
const known = registry.map((d) => d.id).join(', ');

if (!domainId || !source) {
  console.error(
    'Usage: node scripts/build-domain-index.mjs <domain-id> <path/to/annotations.jsonl> [--dry-run]\n' +
      `Known domains: ${known}\n` +
      '--dry-run reports what WOULD be selected and exits before spending anything on embeddings.',
  );
  process.exit(1);
}

const domain = registry.find((d) => d.id === domainId);
if (!domain) {
  console.error(`Unknown domain "${domainId}". Known domains: ${known}`);
  process.exit(1);
}

const ANNOTATIONS = resolve(process.cwd(), source);
const DB_PATH = join(PROJECT, 'src', 'mastra', 'public', domain.dbFile);
const DB_URL = `file:${DB_PATH}`;

const key = process.env.OPENAI_API_KEY;
if (!key && !DRY_RUN) {
  console.error('OPENAI_API_KEY is not set (needed to embed records).');
  process.exit(1);
}

const isUsableDate = (date) =>
  typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date) && date >= '2000-01-01' && date <= SNAPSHOT_MAX;

/**
 * Selector kinds. Each takes the RAW annotation record and answers "is this in the
 * domain?" — selection reads fields the trimmed shape drops, so it runs on the raw record.
 *
 * Keep these NEUTRAL: by body or by sector, never by matching the demo questions.
 */
const SELECTORS = {
  regulatorAllowlist: (values) => {
    const allow = new Set(values.map((s) => s.toLowerCase()));
    return (record) =>
      allow.has((record.output_data?.classification?.regulatory_source?.name ?? '').toLowerCase());
  },
  industryAny: (values) => {
    const want = new Set(values.map((s) => s.toLowerCase()));
    return (record) =>
      (record.output_data?.metadata?.impacted_business?.industry ?? []).some((i) =>
        want.has(String(i).toLowerCase()),
      );
  },
};

const makeSelector = SELECTORS[domain.selector.kind];
if (!makeSelector) {
  console.error(
    `Unknown selector kind "${domain.selector.kind}". Known: ${Object.keys(SELECTORS).join(', ')}`,
  );
  process.exit(1);
}
const inDomain = makeSelector(domain.selector.values);

/** Keeps only the fields the tool shows. Identical across domains, so hits are uniform. */
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

/** The semantic surface we embed: what a user's question would map to. */
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
  if (!line.trim()) continue;
  scanned += 1;
  let record;
  try {
    record = JSON.parse(line);
  } catch {
    continue;
  }
  if (!inDomain(record)) continue;
  const t = trim(record);
  if (!t.title || !isUsableDate(t.date)) continue;
  kept.push(t);
  perBody.set(t.regulator, (perBody.get(t.regulator) ?? 0) + 1);
}

console.log(`domain:   ${domain.id} — ${domain.label}`);
console.log(`scanned:  ${scanned.toLocaleString()} annotation records`);
console.log(`kept:     ${kept.length.toLocaleString()} usable records`);
for (const [body, n] of [...perBody.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12)) {
  console.log(`  ${String(n).padStart(6)}  ${body}`);
}
if (kept.length === 0) {
  console.error('\nNothing matched this domain — refusing to build an empty index.');
  process.exit(1);
}

if (DRY_RUN) {
  const oldest = kept.reduce((a, r) => (r.date < a ? r.date : a), '9999-99-99');
  const newest = kept.reduce((a, r) => (r.date > a ? r.date : a), '');
  console.log(`\ndates:    ${oldest} .. ${newest}`);
  console.log('--dry-run: selection only, nothing embedded, nothing written, $0 spent.');
  process.exit(0);
}

// 2. Embed and upsert.
const store = new LibSQLVector({ id: `carver-${domain.id}-vector`, url: DB_URL });
await store.createIndex({ indexName: domain.indexName, dimension: DIMENSION });

for (let i = 0; i < kept.length; i += BATCH) {
  const slice = kept.slice(i, i + BATCH);
  const vectors = await embedBatch(slice.map(embedText));
  await store.upsert({ indexName: domain.indexName, vectors, metadata: slice });
  console.log(`embedded ${Math.min(i + BATCH, kept.length).toLocaleString()} / ${kept.length.toLocaleString()}`);
}

// 3. Report what actually landed, read back from the DB rather than assumed.
const raw = createClient({ url: DB_URL });
const count = await raw.execute(`SELECT COUNT(*) AS n FROM ${domain.indexName}`);
console.log(
  `done: ${Number(count.rows[0].n).toLocaleString()} records in index "${domain.indexName}" at ${DB_URL}`,
);
console.log('RESTART `npm run dev` so the agent picks up the new index.');
