// How fast is brute-force vector_distance_cos as the table grows? Extrapolates to a full-corpus index.
import { LibSQLVector } from '@mastra/libsql';
const P='/home/ubuntu/work/scribble/code/repos/carver-demos-docs-carver-whitepaper/mastra-studio-demo';
const key=process.env.OPENAI_API_KEY;
const r=await fetch('https://api.openai.com/v1/embeddings',{method:'POST',headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json'},body:JSON.stringify({model:'text-embedding-3-small',input:'authorisation to offer crypto custody services in the EU'})});
const vec=(await r.json()).data[0].embedding;
for (const [db,idx,n] of [['crypto-assets.db','cryptoAssets',1487],['medical-devices.db','medicalDevices',3062],['enforcement.db','enforcement',6451],['state-lending.db','stateLending',7146]]) {
  const store=new LibSQLVector({id:`b-${idx}`,url:`file:${P}/src/mastra/public/${db}`});
  await store.query({indexName:idx,queryVector:vec,topK:5}); // warm
  const t=Date.now(); for(let i=0;i<3;i++) await store.query({indexName:idx,queryVector:vec,topK:5});
  console.log(`${idx.padEnd(15)} ${String(n).padStart(6)} rows → ${((Date.now()-t)/3).toFixed(0)} ms/query`);
}
