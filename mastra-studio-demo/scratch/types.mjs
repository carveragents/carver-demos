import { createClient } from '@libsql/client';
import { readFileSync } from 'node:fs';
const P = '/home/ubuntu/work/scribble/code/repos/carver-demos-docs-carver-whitepaper/mastra-studio-demo';
const domains = JSON.parse(readFileSync(`${P}/data/carver-domains.json`, 'utf8')).domains;
for (const d of domains) {
  let rows; try { rows = (await createClient({url:`file:${P}/src/mastra/public/${d.dbFile}`}).execute(`SELECT metadata FROM ${d.indexName}`)).rows; } catch { continue; }
  const recs = rows.map(r=>JSON.parse(r.metadata));
  const t={}; for (const r of recs) t[r.updateType]=(t[r.updateType]??0)+1;
  console.log(`\n${d.id}: ${Object.entries(t).sort((a,b)=>b[1]-a[1]).map(([k,n])=>`${k}=${n}`).join(' · ')}`);
}
