import { Agent } from '@mastra/core/agent';
import { LENDING_STATUS_BASE_INSTRUCTIONS, ADVISOR_TRIGGER } from './lending-status-instructions.ts';
import { lookupApplicant } from '../tools/lookup-applicant-tool.ts';
import { searchCarverStateLending } from '../tools/carver-state-lending-tool.ts';
import { demoMemory } from '../memory.ts';

/**
 * The treatment: same base instructions and the same verbatim trigger clause as the web arm, plus
 * Carver's curated consumer-lending obligation index. Two function tools (lookupApplicant +
 * searchCarverStateLending), so both are retained. maxSteps cap as on the other Carver arms.
 *
 * The tool description is deliberately plain — it names no state and no obligation. The agent
 * surfaces the applicant's state obligation because it queries the obligation index with the
 * situation the lookup returned, not because it was told state overlays exist.
 *
 * This was NOT true until 2026-07-29. The shipped description had drifted to name both targets
 * outright ("state overlays such as Colorado's AI Act (ADMT) … and California's Holden Act Fair
 * Lending Notice"), i.e. the arm was nudged toward exactly what the demo claims it discovers on
 * merit, while the web arm got no equivalent hint — a live prompt-asymmetry confound sitting
 * directly under a comment asserting the opposite.
 *
 * Re-measured with the description above, naming no state and no statute
 * (`scripts/overlay-hitrate.mjs carver <applicant> 8`):
 *   CO-1001 8/8, CA-1001 8/8 — identical to the nudged version.
 * The win is the data, not the prompt. Keep this description free of state and statute names, and
 * re-run that check if it is ever edited.
 */
export const lendingStatusCarverAgent = new Agent({
  id: 'lending-status-carver-agent',
  name: 'Lending Status — Carver (grounded)',
  description: 'The treatment. Same applicant lookup, plus a Carver-grounded obligation index — jurisdiction-tagged regulatory records, reached as an ordinary Mastra tool.',
  instructions: `${LENDING_STATUS_BASE_INSTRUCTIONS}

You can search Carver's US consumer-lending obligation records with searchCarverStateLending. Each record carries the issuing body, the date, an extracted list of key requirements, and a sourceUrl. Whenever you rely on a record, include its sourceUrl as a markdown link on the title so the reader can check it. Never invent or adjust a URL.

${ADVISOR_TRIGGER}`,
  model: 'openai/gpt-5.6-sol',
  defaultOptions: { maxSteps: 8 },
  tools: { lookupApplicant, searchCarverStateLending },
  memory: demoMemory,
});
