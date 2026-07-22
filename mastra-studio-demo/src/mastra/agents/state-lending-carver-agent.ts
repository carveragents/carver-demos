import { Agent } from '@mastra/core/agent';
import { ADVISOR_BASE_INSTRUCTIONS, ADVISOR_TRIGGER } from './advisor-base-instructions.ts';
import { searchCarverStateLending } from '../tools/carver-state-lending-tool.ts';

/**
 * The treatment for the state-lending counterfactual swap. Same model, same base instructions,
 * same verbatim trigger clause (ADVISOR_TRIGGER) as advisorWebsearchAgent — only the corpus
 * differs. Grounded on the curated federal+state adverse-action obligation index.
 *
 * The tool-intro paragraph names no state and no obligation the swap tests for — if it did, the
 * agent would be reciting the prompt. maxSteps cap as on the other Carver arms.
 */
export const stateLendingCarverAgent = new Agent({
  id: 'state-lending-carver-agent',
  name: 'State-Lending Carver (grounded)',
  instructions: `${ADVISOR_BASE_INSTRUCTIONS}

You can search Carver's US consumer-lending obligation records — the federal ECOA/Regulation B and FCRA baseline plus state-level overlays — with searchCarverStateLending. Each record carries the issuing body, the jurisdiction it applies to, an extracted list of key requirements, and a sourceUrl. Whenever you rely on a record, include its sourceUrl as a markdown link on the title so the reader can check it. Never invent or adjust a URL.

${ADVISOR_TRIGGER}`,
  model: 'openai/gpt-5.6-sol',
  defaultOptions: { maxSteps: 8 },
  tools: { searchCarverStateLending },
});
