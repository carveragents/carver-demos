/**
 * Pre-registration integrity check: every ground-truth record named in questions.json must
 * actually exist in the index the arm will search. A key quoting a record the arm cannot reach
 * is not a hard question, it is a broken one — and it would show up as a Carver "miss" that is
 * really an authoring error.
 *
 * Checks each question's ground_truth against BOTH the full-corpus index (the carver-full arm)
 * and its per-domain index (the carver-domain arm), matching on sourceUrl first and falling
 * back to exact title+date.
 *
 *   node scripts/verify-ground-truth.mjs
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createClient } from '@libsql/client';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = join(HERE, '..');
const domains = JSON.parse(readFileSync(join(PROJECT, 'data', 'carver-domains.json'), 'utf8')).domains;
const spec = JSON.parse(readFileSync(join(PROJECT, 'whitepaper', 'experiments', 'questions.json'), 'utf8'));

const cache = new Map();
const load = async (id) => {
  if (cache.has(id)) return cache.get(id);
  const d = domains.find((x) => x.id === id);
  let recs = [];
  try {
    const rows = (await createClient({ url: `file:${join(PROJECT, 'src', 'mastra', 'public', d.dbFile)}` })
      .execute(`SELECT metadata FROM ${d.indexName}`)).rows;
    recs = rows.map((r) => JSON.parse(r.metadata));
  } catch (err) {
    console.error(`  ! index "${id}" unreadable: ${String(err).slice(0, 90)}`);
  }
  cache.set(id, recs);
  return recs;
};

const findIn = (recs, gt) => {
  if (gt.sourceUrl) {
    const byUrl = recs.filter((r) => r.sourceUrl === gt.sourceUrl);
    if (byUrl.length) return { how: 'url', n: byUrl.length, rec: byUrl[0] };
  }
  const byTitle = recs.filter((r) => r.title === gt.title && r.date === gt.date);
  if (byTitle.length) return { how: 'title+date', n: byTitle.length, rec: byTitle[0] };
  const loose = recs.filter((r) => r.date === gt.date && String(r.title).slice(0, 40) === String(gt.title).slice(0, 40));
  if (loose.length) return { how: 'title-prefix', n: loose.length, rec: loose[0] };
  return null;
};

let ok = 0;
let missingFull = 0;
let missingDomain = 0;
const problems = [];

for (const q of spec.questions) {
  const gt = q.ground_truth;
  if (!gt?.sourceUrl && !gt?.title) {
    console.log(`${q.id}  (no single ground-truth record — multi-record scenario, skipped)`);
    continue;
  }
  const full = findIn(await load('full'), gt);
  const dom = findIn(await load(q.domain), gt);
  const mark = (h) => (h ? `${h.how}${h.n > 1 ? ` x${h.n}` : ''}` : 'MISSING');
  const line = `${q.id}  ${q.stratum.padEnd(18)} ${q.domain.padEnd(16)} full=${mark(full).padEnd(14)} domain=${mark(dom)}`;
  console.log(line);
  if (!full) {
    missingFull += 1;
    problems.push(`${q.id}: not found in FULL index — ${gt.title?.slice(0, 60)}`);
  }
  if (!dom) {
    missingDomain += 1;
    problems.push(`${q.id}: not found in ${q.domain} index — ${gt.title?.slice(0, 60)}`);
  }
  if (full && dom) ok += 1;
}

console.log(`\nreachable in both indices: ${ok} / ${spec.questions.length}`);
console.log(`missing from full index:   ${missingFull}`);
console.log(`missing from domain index: ${missingDomain}`);
if (problems.length) {
  console.log('\nPROBLEMS (each is either a re-source or an explicit, reported caveat):');
  for (const p of problems) console.log(`  - ${p}`);
  process.exitCode = 1;
}
