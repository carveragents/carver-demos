import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  type RawHit,
  runEnforcementSearch,
  shapeHits,
} from './carver-enforcement-search.ts';

const hit = (id: string, score: number, extra: Record<string, unknown> = {}): RawHit => ({
  id,
  score,
  metadata: {
    title: `title-${id}`,
    regulator: 'Federal Trade Commission',
    date: '2026-05-01',
    updateType: 'enforcement',
    whatChanged: 'wc',
    whyItMatters: 'wm',
    keyRequirements: ['kr'],
    impactScore: 8,
    tags: ['earnings'],
    sourceUrl: 'https://ftc.example/1',
    ...extra,
  },
});

test('shapeHits orders by score desc and truncates to limit', () => {
  const out = shapeHits([hit('a', 0.4), hit('b', 0.9), hit('c', 0.7)], 2);
  assert.deepEqual(out.map((h) => h.title), ['title-b', 'title-c']);
});

test('shapeHits drops hits below minScore', () => {
  const out = shapeHits([hit('a', 0.2), hit('b', 0.8)], 5, 0.5);
  assert.equal(out.length, 1);
  assert.equal(out[0].title, 'title-b');
});

test('shapeHits maps metadata onto the record shape and appends score', () => {
  const [only] = shapeHits([hit('a', 0.6)], 1);
  assert.equal(only.regulator, 'Federal Trade Commission');
  assert.equal(only.impactScore, 8);
  assert.equal(only.score, 0.6);
});

test('shapeHits tolerates missing metadata with safe defaults', () => {
  const out = shapeHits([{ id: 'x', score: 0.5 }], 1);
  assert.equal(out[0].title, '');
  assert.equal(out[0].impactScore, null);
  assert.deepEqual(out[0].keyRequirements, []);
  assert.equal(out[0].score, 0.5);
});

test('runEnforcementSearch embeds the query, queries the store, and shapes the result', async () => {
  const calls: { embedded?: string; vector?: number[]; topK?: number } = {};
  const deps = {
    embed: async (text: string) => {
      calls.embedded = text;
      return [1, 2, 3];
    },
    queryVectors: async (vector: number[], topK: number) => {
      calls.vector = vector;
      calls.topK = topK;
      return [hit('b', 0.9), hit('a', 0.3)];
    },
  };

  const out = await runEnforcementSearch(deps, 'what returns can I expect?', 2);

  assert.equal(calls.embedded, 'what returns can I expect?');
  assert.deepEqual(calls.vector, [1, 2, 3]);
  assert.equal(calls.topK, 2);
  assert.deepEqual(out.map((h) => h.title), ['title-b', 'title-a']);
});
