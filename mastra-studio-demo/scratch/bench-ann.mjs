/**
 * Can a COMPRESSED DiskANN index make a full-corpus (244k) index queryable?
 * The build script drops DiskANN because the default costs ~320 KB/vector (78 GB at 244k).
 * libsql supports compress_neighbors + max_neighbors, which should cut that hugely.
 * Test on a copy of state-lending (7,146 rows) and extrapolate.
 */
import { createClient } from '@libsql/client';
import { statSync } from 'node:fs';
const DB = '/tmp/claude-1000/-home-ubuntu-work-scribble-code-repos-carver-demos/dd819034-45a1-41a3-9f2e-b222986ada64/scratchpad/ann-test.db';
const c = createClient({ url: `file:${DB}` });
const N = 7146;
const before = statSync(DB).size;
const key = process.env.OPENAI_API_KEY;
const r = await fetch('https://api.openai.com/v1/embeddings', { method: 'POST', headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ model: 'text-embedding-3-small', input: 'adverse action notice obligations for a declined consumer loan applicant' }) });
const vec = (await r.json()).data[0].embedding;
const lit = `vector32('[${vec.join(',')}]')`;

console.log(`table: stateLending, ${N} rows, db ${(before / 1e6).toFixed(0)} MB`);
let t = Date.now();
await c.execute(`SELECT id FROM stateLending ORDER BY vector_distance_cos(embedding, ${lit}) LIMIT 5`);
console.log(`brute force:            ${Date.now() - t} ms`);

t = Date.now();
await c.execute(`CREATE INDEX IF NOT EXISTS sl_ann ON stateLending(libsql_vector_idx(embedding, 'metric=cosine', 'compress_neighbors=float8', 'max_neighbors=20'))`);
const buildMs = Date.now() - t;
const after = statSync(DB).size;
console.log(`ANN build:              ${buildMs} ms → +${((after - before) / 1e6).toFixed(0)} MB  (${((after - before) / N / 1024).toFixed(1)} KB/vector)`);

t = Date.now();
for (let i = 0; i < 3; i++) await c.execute(`SELECT id FROM vector_top_k('sl_ann', ${lit}, 5)`);
console.log(`ANN query:              ${((Date.now() - t) / 3).toFixed(0)} ms`);

const perVecKB = (after - before) / N / 1024;
console.log(`\nEXTRAPOLATION to 244,297 records:`);
console.log(`  ANN index size ≈ ${(perVecKB * 244297 / 1024 / 1024).toFixed(1)} GB`);
console.log(`  build time     ≈ ${(buildMs * (244297 / N) / 60000).toFixed(0)} min`);
console.log(`  brute force    ≈ ${(0.37 * 244297 / 1000).toFixed(0)} s/query  (unusable)`);
