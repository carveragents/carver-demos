import { Agent } from '@mastra/core/agent';
import { ADVISOR_BASE_INSTRUCTIONS } from './advisor-base-instructions.ts';

/**
 * The control: no tools, no grounding. Answers from model memory alone.
 *
 * Not told that it lacks data and not told to be cautious — a hedging baseline would be as
 * misleading as a sandbagged one. Whatever caution it shows is what `gpt-5.6-sol` does on its
 * own, which is the quantity the mini-suite measures against. Shared across all three domains.
 */
export const advisorBaselineAgent = new Agent({
  id: 'advisor-baseline-agent',
  name: 'Advisor Baseline (no data)',
  instructions: ADVISOR_BASE_INSTRUCTIONS,
  model: 'openai/gpt-5.6-sol',
});
