/**
 * Pull FULL records (no truncation) for the specific candidates chosen as question sources,
 * so the pre-registered answer keys quote the corpus verbatim rather than a summary of it.
 *
 *   node scratch/fetch-records.mjs <domain> <date> <title-substring>
 * Repeatable via a spec file: node scratch/fetch-records.mjs --spec <file.tsv>  (domain\tdate\tsubstr)
 */
import { createClient } from '@libsql/client';
import { readFileSync } from 'node:fs';

const P = '/home/ubuntu/work/scribble/code/repos/carver-demos-docs-carver-whitepaper/mastra-studio-demo';
const domains = JSON.parse(readFileSync(`${P}/data/carver-domains.json`, 'utf8')).domains;
const cache = new Map();

const load = async (id) => {
  if (cache.has(id)) return cache.get(id);
  const d = domains.find((x) => x.id === id);
  const rows = (await createClient({ url: `file:${P}/src/mastra/public/${d.dbFile}` }).execute(`SELECT metadata FROM ${d.indexName}`)).rows;
  const recs = rows.map((r) => JSON.parse(r.metadata));
  cache.set(id, recs);
  return recs;
};

const specs = process.argv[2] === '--spec'
  ? readFileSync(process.argv[3], 'utf8').split('\n').filter((l) => l.trim() && !l.startsWith('#')).map((l) => l.split('\t'))
  : [process.argv.slice(2, 5)];

for (const [domain, date, substr] of specs) {
  const recs = await load(domain);
  const hits = recs.filter((r) => r.date === date && String(r.title).toLowerCase().includes(String(substr).toLowerCase()));
  console.log(`\n${'='.repeat(100)}\n@@ ${domain} | ${date} | "${substr}" → ${hits.length} match(es)`);
  for (const r of hits.slice(0, 2)) console.log(JSON.stringify(r, null, 2));
}
