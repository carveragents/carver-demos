import { Agent } from '@mastra/core/agent';
import { ADVISOR_BASE_INSTRUCTIONS, ADVISOR_TRIGGER } from './advisor-base-instructions.ts';
import { searchCarverChildSafety } from '../tools/carver-child-safety-tool.ts';

/**
 * The treatment for the online-child-safety scenario. Same model, same base instructions, same
 * verbatim trigger clause (ADVISOR_TRIGGER) as advisorWebsearchAgent — only the corpus differs.
 * Search-only; see cryptoCarverAgent for the rationale.
 */
export const childSafetyCarverAgent = new Agent({
  id: 'child-safety-carver-agent',
  name: 'Child-Safety Carver (grounded)',
  instructions: `${ADVISOR_BASE_INSTRUCTIONS}

You can search Carver's online child-safety and data-protection regulatory signals — age assurance, minors' data, and platform-conduct records from bodies such as the ICO, the Garante, CNIL, the FTC and the FCC — with searchCarverChildSafety. Each record carries the issuing body, the date, an extracted list of key requirements, and a sourceUrl. Whenever you rely on a record, include its sourceUrl as a markdown link on the title so the reader can check it. Never invent or adjust a URL.

${ADVISOR_TRIGGER}`,
  model: 'openai/gpt-5.6-sol',
  // Cap the retrieval loop so the interactive Studio demo cannot thrash — see cryptoCarverAgent.
  defaultOptions: { maxSteps: 8 },
  tools: { searchCarverChildSafety },
});
