import { Agent } from '@mastra/core/agent';
import { LENDING_STATUS_BASE_INSTRUCTIONS, ADVISOR_TRIGGER } from './lending-status-instructions.ts';
import { lookupApplicant } from '../tools/lookup-applicant-tool.ts';
import { searchCarverStateLending } from '../tools/carver-state-lending-tool.ts';

/**
 * The treatment: same base instructions and the same verbatim trigger clause as the web arm, plus
 * Carver's curated consumer-lending obligation index. Two function tools (lookupApplicant +
 * searchCarverStateLending), so both are retained. maxSteps cap as on the other Carver arms.
 *
 * The tool description is deliberately plain — it names no state and no obligation (see the
 * confound check in docs/DEMO.md). The agent surfaces the applicant's state obligation because it
 * queries the obligation index with the situation the lookup returned, not because it was told
 * state overlays exist.
 */
export const lendingStatusCarverAgent = new Agent({
  id: 'lending-status-carver-agent',
  name: 'Lending Status — Carver (grounded)',
  instructions: `${LENDING_STATUS_BASE_INSTRUCTIONS}

You can search Carver's US consumer-lending obligation records with searchCarverStateLending. Each record carries the issuing body, the date, an extracted list of key requirements, and a sourceUrl. Whenever you rely on a record, include its sourceUrl as a markdown link on the title so the reader can check it. Never invent or adjust a URL.

${ADVISOR_TRIGGER}`,
  model: 'openai/gpt-5.6-sol',
  defaultOptions: { maxSteps: 8 },
  tools: { lookupApplicant, searchCarverStateLending },
});
