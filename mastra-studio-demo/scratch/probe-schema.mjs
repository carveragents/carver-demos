import { createClient } from '@libsql/client';
const c = createClient({ url: 'file:/tmp/claude-1000/-home-ubuntu-work-scribble-code-repos-carver-demos/dd819034-45a1-41a3-9f2e-b222986ada64/scratchpad/ann-test.db' });
console.log('SCHEMA:', (await c.execute(`SELECT sql FROM sqlite_master WHERE name='stateLending'`)).rows[0].sql);
const key = process.env.OPENAI_API_KEY;
const r = await fetch('https://api.openai.com/v1/embeddings', { method:'POST', headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json'}, body: JSON.stringify({model:'text-embedding-3-small',input:'adverse action notice for a declined loan applicant in Colorado'})});
const v = JSON.stringify((await r.json()).data[0].embedding);
const t = Date.now();
const res = await c.execute({
  sql: `SELECT f.rowid AS id,
               1 - vector_distance_cos(f.embedding, vector32(?)) AS score,
               f.metadata AS metadata
        FROM vector_top_k('sl_ann', vector32(?), ?) AS v
        JOIN stateLending AS f ON f.rowid = v.id
        ORDER BY score DESC`,
  args: [v, v, 5],
});
console.log(`ANN join query: ${Date.now()-t} ms, ${res.rows.length} rows`);
for (const row of res.rows) {
  const m = JSON.parse(row.metadata);
  console.log(`  ${row.score.toFixed(3)}  [${m.date}] ${m.regulator?.slice(0,40)}: ${m.title?.slice(0,70)}`);
}
