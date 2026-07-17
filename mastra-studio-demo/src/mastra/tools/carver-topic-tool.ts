import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { loadTopics, searchTopics } from './carver-topic-search.ts';

// Loaded once at startup: ~150 records, so no index or cache is warranted. A missing or
// malformed fixture throws here, at `mastra dev` boot, rather than mid-demo.
const topics = loadTopics();

const topicSchema = z.object({
  name: z.string(),
  acronym: z.string(),
  jurisdiction: z.string(),
  system: z.string(),
  sector: z.string(),
  industry: z.string(),
  subIndustry: z.string(),
  confidence: z.string(),
});

export const searchCarverTopics = createTool({
  id: 'search-carver-topics',
  description:
    "Look up a regulatory body in Carver's topic taxonomy by name or acronym, and return its " +
    'sector/industry classification. Many acronyms are ambiguous across jurisdictions, so this ' +
    'can return several bodies for one query.',
  inputSchema: z.object({
    query: z.string().min(1).describe('A regulator name or acronym, e.g. "SEC" or "Bank of England"'),
    limit: z.number().int().positive().optional().describe('Max matches to return (default 5)'),
  }),
  outputSchema: z.object({
    matchCount: z.number().describe('Total matches found, before any truncation by limit'),
    matches: z.array(topicSchema),
  }),
  execute: async (inputData) => {
    const { matchCount, matches } = searchTopics(topics, inputData.query, inputData.limit ?? 5);

    return {
      matchCount,
      matches: matches.map(({ topicId, ...rest }) => rest),
    };
  },
});
