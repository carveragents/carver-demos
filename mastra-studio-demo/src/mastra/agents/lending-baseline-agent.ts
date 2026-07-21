import { Agent } from '@mastra/core/agent';
import { LENDING_BASE_INSTRUCTIONS } from './lending-base-instructions.ts';

/**
 * The control: no tools, no grounding. Answers from model memory alone.
 *
 * Not told that it lacks data and not told to be cautious — a hedging baseline would be as
 * misleading as a sandbagged one. Whatever caution it shows is what `gpt-5.6-sol` does on its
 * own, which is exactly the quantity the demo needs to measure against.
 */
export const lendingBaselineAgent = new Agent({
  id: 'lending-baseline-agent',
  name: 'Lending Baseline (no data)',
  instructions: LENDING_BASE_INSTRUCTIONS,
  model: 'openai/gpt-5.6-sol',
});
