/**
 * Minimal OpenAI embeddings client (text-embedding-3-small, 1536-dim) over REST. No @ai-sdk
 * dependency — consistent with this project's "the model is a router string" convention.
 * Used at runtime to embed the user's query. (The build script embeds documents with its own
 * copy, because it is .mjs and cannot import this .ts module cleanly under typecheck.)
 */
const ENDPOINT = 'https://api.openai.com/v1/embeddings';
const MODEL = 'text-embedding-3-small';

/** Embed many strings in one request; output order matches input order. */
export async function embedBatch(texts: string[]): Promise<number[][]> {
  const key = process.env.OPENAI_API_KEY;
  if (!key) throw new Error('OPENAI_API_KEY is not set');

  const res = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: MODEL, input: texts }),
  });
  if (!res.ok) {
    throw new Error(`embeddings request failed: ${res.status} ${await res.text()}`);
  }

  const json = (await res.json()) as { data: { index: number; embedding: number[] }[] };
  return json.data.sort((a, b) => a.index - b.index).map((d) => d.embedding);
}

/** Embed a single string. */
export async function embed(text: string): Promise<number[]> {
  const [vector] = await embedBatch([text]);
  return vector;
}
