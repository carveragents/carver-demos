import { Agent } from '@mastra/core/agent';
import { BASE_INSTRUCTIONS } from './base-instructions.ts';

/**
 * The control in the demo: no tools, no data. Answers from model memory alone.
 * Nothing here weakens it — it is not sandbagged, just ungrounded.
 */
export const baselineAgent = new Agent({
  id: 'baseline-agent',
  name: 'Baseline Agent (no data)',
  instructions: BASE_INSTRUCTIONS,
  model: 'openai/gpt-5.6-sol',
});
