/** Does the 229k ANN index actually answer fast, and with the right records? */
import { createClient } from '@libsql/client';
const c = createClient({ url: 'file:src/mastra/public/full.db' });
const key = process.env.OPENAI_API_KEY;
const emb = async (t) => {
  const r = await fetch('https://api.openai.com/v1/embeddings', { method:'POST', headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json'}, body: JSON.stringify({model:'text-embedding-3-small',input:t})});
  return JSON.stringify((await r.json()).data[0].embedding);
};
const QUERIES = [
  'registration required before placing in-vitro diagnostic devices on the Swiss market',
  'payment institution authorisation for e-money token crypto services in France',
  'preemption of state interchange fee law for national banks',
  'advance notice before discontinuing supply of a medical device',
];
for (const q of QUERIES) {
  const v = await emb(q);
  const t = Date.now();
  const res = await c.execute({
    sql: `SELECT f.rowid AS id, 1 - vector_distance_cos(f.embedding, vector32(?)) AS score, f.metadata AS metadata
          FROM vector_top_k('fullCorpus_ann', vector32(?), ?) AS v
          JOIN fullCorpus AS f ON f.rowid = v.id ORDER BY score DESC`,
    args: [v, v, 3],
  });
  console.log(`\n[${Date.now()-t} ms] ${q}`);
  for (const row of res.rows) {
    const m = JSON.parse(row.metadata);
    console.log(`   ${row.score.toFixed(3)} [${m.date}] ${String(m.regulator).slice(0,34)}: ${String(m.title).slice(0,62)}`);
  }
}
