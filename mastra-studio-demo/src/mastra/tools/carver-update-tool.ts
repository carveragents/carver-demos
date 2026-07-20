import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { loadTopics } from './carver-topic-search.ts';
import { loadUpdates, searchUpdates } from './carver-update-search.ts';

// Loaded once at startup: ~1,000 records. A missing or malformed fixture throws here, at
// `mastra dev` boot, rather than mid-demo.
const topics = loadTopics();
const updates = loadUpdates();

const updateSchema = z.object({
  title: z.string(),
  date: z.string().describe('Publication date, YYYY-MM-DD'),
  updateType: z.string(),
  regulator: z.string(),
  country: z.string(),
  impact: z.string(),
  impactScore: z.number().nullable(),
  urgency: z.string(),
  whatChanged: z.string(),
  whyItMatters: z.string(),
  keyRequirements: z.array(z.string()),
  tags: z.array(z.string()),
  sourceUrl: z
    .string()
    .describe(
      "Direct link to the source document on the regulator's own site. Cite this whenever " +
        'you reference the update, so the reader can verify the claim.',
    ),
});

export const searchCarverUpdates = createTool({
  id: 'search-carver-updates',
  description:
    'Find regulatory documents a body has published recently, from Carver\'s annotated dataset. ' +
    'Returns dated updates newest first, with impact and urgency scoring, what changed, and why ' +
    'it matters. Use for any question about recent regulatory activity, news, or changes.',
  inputSchema: z.object({
    regulator: z
      .string()
      .min(1)
      .describe('A regulator name or acronym, e.g. "FCA" or "European Central Bank"'),
    keyword: z
      .string()
      .optional()
      .describe('Optional topic filter, e.g. "crypto". Matches title, tags, and what changed.'),
    limit: z.number().int().positive().optional().describe('Max updates to return (default 5)'),
  }),
  outputSchema: z.object({
    matchCount: z.number().describe('Total updates found, before any truncation by limit'),
    ambiguousRegulators: z
      .array(z.object({ name: z.string(), acronym: z.string(), jurisdiction: z.string() }))
      .describe('Populated when the name matched more than one body; updates cover all of them'),
    updates: z.array(updateSchema),
  }),
  execute: async (inputData) => {
    const result = searchUpdates(topics, updates, {
      regulator: inputData.regulator,
      keyword: inputData.keyword,
      limit: inputData.limit ?? 5,
    });

    return {
      matchCount: result.matchCount,
      ambiguousRegulators: result.ambiguousRegulators,
      updates: result.updates.map(({ topicId, ...rest }) => rest),
    };
  },
});
