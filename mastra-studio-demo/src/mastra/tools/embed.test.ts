import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { embed, embedBatch } from './embed.ts';

const realFetch = globalThis.fetch;
const realKey = process.env.OPENAI_API_KEY;

afterEach(() => {
  globalThis.fetch = realFetch;
  if (realKey === undefined) delete process.env.OPENAI_API_KEY;
  else process.env.OPENAI_API_KEY = realKey;
});

test('embedBatch posts to the embeddings endpoint with the model and input, ordered by index', async () => {
  process.env.OPENAI_API_KEY = 'sk-test';
  let captured: { url: string; body: any; auth: string } | undefined;
  globalThis.fetch = (async (url: any, init: any) => {
    captured = {
      url: String(url),
      body: JSON.parse(init.body),
      auth: init.headers.Authorization,
    };
    return {
      ok: true,
      json: async () => ({
        data: [
          { index: 1, embedding: [0.4, 0.5] },
          { index: 0, embedding: [0.1, 0.2] },
        ],
      }),
    };
  }) as unknown as typeof fetch;

  const out = await embedBatch(['first', 'second']);

  assert.equal(captured?.url, 'https://api.openai.com/v1/embeddings');
  assert.equal(captured?.auth, 'Bearer sk-test');
  assert.equal(captured?.body.model, 'text-embedding-3-small');
  assert.deepEqual(captured?.body.input, ['first', 'second']);
  assert.deepEqual(out, [
    [0.1, 0.2],
    [0.4, 0.5],
  ]);
});

test('embed returns the single vector', async () => {
  process.env.OPENAI_API_KEY = 'sk-test';
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({ data: [{ index: 0, embedding: [9, 8, 7] }] }),
  })) as unknown as typeof fetch;

  assert.deepEqual(await embed('hi'), [9, 8, 7]);
});

test('embedBatch throws when the key is missing', async () => {
  delete process.env.OPENAI_API_KEY;
  await assert.rejects(() => embedBatch(['x']), /OPENAI_API_KEY/);
});

test('embedBatch throws on a non-ok response', async () => {
  process.env.OPENAI_API_KEY = 'sk-test';
  globalThis.fetch = (async () => ({
    ok: false,
    status: 429,
    text: async () => 'rate limited',
  })) as unknown as typeof fetch;

  await assert.rejects(() => embedBatch(['x']), /429/);
});
