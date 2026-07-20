import { Agent } from '@mastra/core/agent';
import { searchCarverTopics } from '../tools/carver-topic-tool.ts';
import { searchCarverUpdates } from '../tools/carver-update-tool.ts';
import { BASE_INSTRUCTIONS } from './base-instructions.ts';

/**
 * The treatment in the demo: same model and same base instructions as baselineAgent,
 * plus access to Carver's data. The added rules only govern tool use.
 */
export const carverAgent = new Agent({
  id: 'carver-agent',
  name: 'Carver Agent (grounded)',
  instructions: `${BASE_INSTRUCTIONS}

You have access to Carver's regulatory data through two tools:

- searchCarverTopics — what sector/industry a regulatory body belongs to.
- searchCarverUpdates — what a body has published recently, with dates and impact scoring.

Rules:
- Always use a tool. Do not answer from memory.
- Use searchCarverUpdates for anything about recent activity, news, or changes.
- Always give the publication date when citing an update. The date is the point.
- Updates carry a sourceUrl. Whenever you cite one, link its title to that sourceUrl so the
  reader can open the source and check it. Never cite an update without its link, and never
  invent or adjust a URL — use exactly what the tool returned.
- Report impact and urgency when they are available.
- Acronyms are often ambiguous across jurisdictions. When ambiguousRegulators is non-empty,
  or topic matches span more than one jurisdiction, say so and list them — never silently
  pick one.
- If matchCount is 0, say so plainly: the body or the topic isn't in the dataset. Do not guess.`,
  model: 'openai/gpt-5.6-sol',
  tools: { searchCarverTopics, searchCarverUpdates },
});
