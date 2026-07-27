/**
 * Phase 1 sourcing, second pass. The first pass (mine-candidates.mjs) ranked by impactScore and
 * surfaced mostly enforcement actions against NAMED third parties — those tell an operator
 * nothing about their own duties, so they make poor question material.
 *
 * This pass keeps only records that read as a GENERALLY-APPLICABLE duty: rule/guidance-class
 * updateTypes, duty language, and no case-caption markers (v., Consent Order, Desist and
 * Refrain, Warning Letter to a named firm…).
 *
 *   node scratch/mine-rules.mjs <domain-id> <from> <to> [limit]
 */
import { createClient } from '@libsql/client';
import { readFileSync } from 'node:fs';

const P = '/home/ubuntu/work/scribble/code/repos/carver-demos-docs-carver-whitepaper/mastra-studio-demo';
const domains = JSON.parse(readFileSync(`${P}/data/carver-domains.json`, 'utf8')).domains;
const [domainId, from = '0000', to = '9999', limitArg = '30'] = process.argv.slice(2);
const d = domains.find((x) => x.id === domainId);
if (!d) { console.error(`Known: ${domains.map((x) => x.id).join(', ')}`); process.exit(1); }

const RULE_TYPES = new Set(['final rule', 'guidance', 'regulation', 'advisory', 'bulletin', 'standard', 'recommendation', 'notice']);
// Case captions and one-off actions against a named party — an operator's duties don't live here.
const CASE = /\bv\.\s|\bvs\.\s| et al\b|consent order|desist and refrain|cease and desist|warning letter|stipulated order|permanent injunction|revoking|revocation of|accusation |taking possession|litigation release|indict|plea |sentenc|settle(s|ment|d)? (with|against)|pay(s)? \$?\d|penalt(y|ies) (of|against)/i;
const DUTY = /\bmust\b|\bshall\b|\brequired to\b|\brequirement/i;
const DATED = /\b(by|from|before|no later than|effective|as of|commenc|deadline|enter(s|ed)? into force|applies from)\b/i;
const ASCII = (s) => (String(s).match(/[\x20-\x7E]/g) ?? []).length / Math.max(1, String(s).length);

const rows = (await createClient({ url: `file:${P}/src/mastra/public/${d.dbFile}` }).execute(`SELECT metadata FROM ${d.indexName}`)).rows;
const recs = rows.map((r) => JSON.parse(r.metadata));

const seen = new Set();
const hits = recs
  .filter((r) => r.date >= from && r.date <= to)
  .filter((r) => RULE_TYPES.has(r.updateType))
  .filter((r) => Array.isArray(r.keyRequirements) && r.keyRequirements.length >= 2 && r.sourceUrl && r.regulator)
  .filter((r) => ASCII(`${r.title} ${r.whatChanged}`) > 0.98)
  .filter((r) => !CASE.test(`${r.title} ${r.whatChanged}`))
  .filter((r) => {
    const blob = `${r.whatChanged} ${r.keyRequirements.join(' ')}`;
    return DUTY.test(blob) && DATED.test(blob);
  })
  .filter((r) => { const k = String(r.title).toLowerCase().slice(0, 60); if (seen.has(k)) return false; seen.add(k); return true; })
  .sort((a, b) => (b.impactScore ?? 0) - (a.impactScore ?? 0) || b.date.localeCompare(a.date))
  .slice(0, Number(limitArg));

console.log(`# ${domainId} — ${hits.length} generally-applicable duty records in [${from} … ${to}]\n`);
for (const r of hits) {
  console.log(`--- [${r.date}] impact=${r.impactScore} · ${r.updateType} · ${r.regulator}`);
  console.log(`    ${r.title}`);
  console.log(`    what: ${String(r.whatChanged).slice(0, 300)}`);
  console.log(`    reqs: ${r.keyRequirements.slice(0, 5).map((k) => `• ${String(k).slice(0, 170)}`).join('\n          ')}`);
  console.log(`    tags: ${(r.tags ?? []).slice(0, 8).join(', ')}`);
  console.log(`    url:  ${r.sourceUrl}\n`);
}
