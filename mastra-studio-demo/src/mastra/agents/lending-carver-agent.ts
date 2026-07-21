import { Agent } from '@mastra/core/agent';
import { searchCarverEnforcement } from '../tools/carver-enforcement-tool.ts';
import { LENDING_BASE_INSTRUCTIONS } from './lending-base-instructions.ts';

/**
 * The treatment: same model and same base instructions as the other two lending arms, plus
 * Carver's enforcement corpus.
 *
 * The added instruction governs tool use only and is topic-agnostic — it never mentions
 * adverse action, Regulation B, military borrowers, or any other obligation the probes ask
 * about. If it named them, the agent would be reciting the prompt rather than retrieving, and
 * the measurement would be worthless. Its trigger clause is worded identically to
 * `lending-websearch-agent`'s so the only variable between them is the corpus.
 *
 * Search only, no query tool. The query tool answers counting and grouping questions; these
 * probes are about whether an obligation is noticed at all, and an extra tool invites the
 * multi-hundred-call thrashing documented in docs/DEMO.md.
 */
export const lendingCarverAgent = new Agent({
  id: 'lending-carver-agent',
  name: 'Lending Carver (grounded)',
  instructions: `${LENDING_BASE_INSTRUCTIONS}

You can search Carver's regulatory signals from the FTC, SEC, CFTC, and CFPB with searchCarverEnforcement. Each record carries an extracted list of key requirements.

Before you communicate a credit decision, state what the company is required to do, or tell someone what they are entitled to, search first and let what you find govern your answer.

Every retrieved record carries a sourceUrl. Whenever you rely on a record, include its sourceUrl as a markdown link on the title so the reader can open the source and check it. Never cite a record without its link, and never invent or adjust a URL — use exactly what the search returned. If you cannot find something, say so plainly rather than answering from memory.`,
  model: 'openai/gpt-5.6-sol',
  tools: { searchCarverEnforcement },
});
