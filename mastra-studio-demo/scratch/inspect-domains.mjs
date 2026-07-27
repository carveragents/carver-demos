/**
 * Inspect the BUILT domain indices — the corpus the Carver arm can actually reach.
 * Ground truth for the experiment must come from here, not from the newer raw snapshot,
 * or the keys and the arm would be reading different corpora.
 */
import { createClient } from '@libsql/client';
import { readFileSync } from 'node:fs';

const PROJECT = '/home/ubuntu/work/scribble/code/repos/carver-demos-docs-carver-whitepaper/mastra-studio-demo';
const domains = JSON.parse(readFileSync(`${PROJECT}/data/carver-domains.json`, 'utf8')).domains;

for (const d of domains) {
  const client = createClient({ url: `file:${PROJECT}/src/mastra/public/${d.dbFile}` });
  let rows;
  try {
    rows = (await client.execute(`SELECT metadata FROM ${d.indexName}`)).rows;
  } catch (err) {
    console.log(`\n### ${d.id}: NOT BUILT (${String(err).slice(0, 80)})`);
    continue;
  }
  const recs = rows.map((r) => JSON.parse(r.metadata));
  const byReg = {};
  const byYear = {};
  for (const r of recs) {
    byReg[r.regulator] = (byReg[r.regulator] ?? 0) + 1;
    byYear[(r.date ?? '????').slice(0, 4)] = (byYear[(r.date ?? '????').slice(0, 4)] ?? 0) + 1;
  }
  const dates = recs.map((r) => r.date).filter(Boolean).sort();
  console.log(`\n### ${d.id} — ${recs.length} records | ${dates[0]} … ${dates[dates.length - 1]}`);
  console.log(`  years: ${Object.entries(byYear).sort().map(([y, n]) => `${y}:${n}`).join(' ')}`);
  console.log(`  top regulators: ${Object.entries(byReg).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k, n]) => `${k} (${n})`).join(' · ')}`);
  const recent = recs.filter((r) => r.date >= '2026-01-01').sort((a, b) => b.date.localeCompare(a.date));
  console.log(`  2026 records: ${recent.length}`);
  console.log(`  sample recent: ${recent.slice(0, 5).map((r) => `[${r.date}] ${r.regulator}: ${String(r.title).slice(0, 70)}`).join('\n                 ')}`);
  // What keys does a record carry? (schema check for ground-truth authoring)
  if (recs[0]) console.log(`  fields: ${Object.keys(recs[0]).join(', ')}`);
}
