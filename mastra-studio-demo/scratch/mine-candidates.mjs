/**
 * Phase 1 sourcing: find records in the BUILT domain indices that carry a real, checkable
 * obligation — the raw material for pre-registered answer keys.
 *
 * A usable candidate has: non-empty keyRequirements, a named regulator, a date, a sourceUrl,
 * and prose that reads as an obligation rather than a press release. Ranked by impactScore.
 *
 *   node scratch/mine-candidates.mjs <domain-id> [from-date] [to-date] [limit]
 */
import { createClient } from '@libsql/client';
import { readFileSync } from 'node:fs';

const PROJECT = '/home/ubuntu/work/scribble/code/repos/carver-demos-docs-carver-whitepaper/mastra-studio-demo';
const domains = JSON.parse(readFileSync(`${PROJECT}/data/carver-domains.json`, 'utf8')).domains;

const [domainId, from = '0000', to = '9999', limitArg = '25'] = process.argv.slice(2);
const d = domains.find((x) => x.id === domainId);
if (!d) {
  console.error(`Unknown domain. Known: ${domains.map((x) => x.id).join(', ')}`);
  process.exit(1);
}

const client = createClient({ url: `file:${PROJECT}/src/mastra/public/${d.dbFile}` });
const rows = (await client.execute(`SELECT metadata FROM ${d.indexName}`)).rows;
const recs = rows.map((r) => JSON.parse(r.metadata));

// Heuristics for "carries an obligation": requirements present and worded as duties.
const DUTY = /\bmust\b|\brequire|\bshall\b|\bmandat|deadline|by \d{1,2} \w+ 20\d\d|no later than|obligat|comply|complian|prohibit|ban(ned)?\b|notify|register|file |submit|disclos/i;
const ASCII = (s) => (String(s).match(/[\x20-\x7E]/g) ?? []).length / Math.max(1, String(s).length);

const scored = recs
  .filter((r) => r.date >= from && r.date <= to)
  .filter((r) => Array.isArray(r.keyRequirements) && r.keyRequirements.length >= 2)
  .filter((r) => r.sourceUrl && r.regulator && r.title)
  .filter((r) => ASCII(`${r.title} ${r.whatChanged}`) > 0.97) // English/Latin-script only
  .filter((r) => DUTY.test(`${r.title} ${r.whatChanged} ${r.whyItMatters} ${r.keyRequirements.join(' ')}`))
  .sort((a, b) => (b.impactScore ?? 0) - (a.impactScore ?? 0) || b.date.localeCompare(a.date))
  .slice(0, Number(limitArg));

console.log(`# ${domainId} — ${scored.length} obligation-bearing candidates in [${from} … ${to}] (of ${recs.length} records)\n`);
for (const r of scored) {
  console.log(`--- [${r.date}] impact=${r.impactScore} · ${r.updateType} · ${r.regulator}`);
  console.log(`    ${r.title}`);
  console.log(`    what: ${String(r.whatChanged).slice(0, 260)}`);
  console.log(`    why:  ${String(r.whyItMatters).slice(0, 200)}`);
  console.log(`    reqs: ${r.keyRequirements.slice(0, 4).map((k) => `• ${String(k).slice(0, 150)}`).join('\n          ')}`);
  console.log(`    tags: ${(r.tags ?? []).slice(0, 8).join(', ')}`);
  console.log(`    url:  ${r.sourceUrl}\n`);
}
