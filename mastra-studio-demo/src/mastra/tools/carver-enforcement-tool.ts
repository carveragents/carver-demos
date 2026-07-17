import { createTool } from '@mastra/core/tools';
import { LibSQLVector } from '@mastra/libsql';
import { z } from 'zod';
import {
  type RawHit,
  runEnforcementSearch,
} from './carver-enforcement-search.ts';
import { embed } from './embed.ts';

// These MUST match scripts/build-enforcement.mjs. They can't be shared by import (that file
// is .mjs, this is .ts), so they are duplicated deliberately and kept in sync by convention.
// `mastra dev` runs with CWD = src/mastra/public (where its own mastra.db lands), so this
// relative path resolves to src/mastra/public/enforcement.db — which is exactly where the
// build script writes the corpus. Keep the two in sync.
export const DB_URL = 'file:./enforcement.db';
export const INDEX_NAME = 'enforcement';
const DEFAULT_LIMIT = 5;

// Owned here, like carver-update-tool.ts owns its loaded fixture. Points at the DB the build
// script writes; opening a not-yet-built store is fine — queries just fail and we degrade.
const store = new LibSQLVector({ id: 'carver-enforcement-vector', url: DB_URL });

const queryVectors = async (vector: number[], topK: number): Promise<RawHit[]> => {
  try {
    return (await store.query({
      indexName: INDEX_NAME,
      queryVector: vector,
      topK,
    })) as RawHit[];
  } catch {
    // Index missing/empty -> the one-time `npm run build:enforcement` step hasn't run.
    // Degrade to no results so the agent says it found nothing rather than crashing.
    return [];
  }
};

const signalSchema = z.object({
  title: z.string(),
  regulator: z.string(),
  date: z.string().describe('Publication date, YYYY-MM-DD'),
  updateType: z.string(),
  whatChanged: z.string(),
  whyItMatters: z.string(),
  keyRequirements: z.array(z.string()),
  impactScore: z.number().nullable(),
  tags: z.array(z.string()),
  sourceUrl: z.string(),
  score: z.number().describe('Semantic similarity to the query, higher is closer'),
});

export const searchCarverEnforcement = createTool({
  id: 'search-carver-enforcement',
  description:
    "Search Carver's regulatory enforcement signals from the FTC, SEC, CFTC, and CFPB by " +
    'meaning. Returns the most semantically similar enforcement actions and guidance, with ' +
    'the regulator, date, what changed, why it matters, and an impact score. Use to ground ' +
    'claims about returns, refunds, testimonials, guarantees, or what regulators have acted on.',
  inputSchema: z.object({
    query: z
      .string()
      .min(1)
      .describe('A natural-language description of the claim or topic to check, e.g. "promising specific investment returns"'),
    limit: z.number().int().positive().optional().describe('Max signals to return (default 5)'),
  }),
  outputSchema: z.object({
    matchCount: z.number().describe('Number of signals returned'),
    signals: z.array(signalSchema),
  }),
  execute: async (inputData) => {
    const hits = await runEnforcementSearch(
      { embed, queryVectors },
      inputData.query,
      inputData.limit ?? DEFAULT_LIMIT,
    );
    return { matchCount: hits.length, signals: hits };
  },
});
