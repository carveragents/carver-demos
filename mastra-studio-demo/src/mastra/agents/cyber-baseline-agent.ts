import { Agent } from '@mastra/core/agent';
import { CYBER_BASE_INSTRUCTIONS } from './cyber-base-instructions.ts';

/**
 * The control: a competent security-operations assistant with no tools and no advisory data.
 * It answers from model memory alone.
 *
 * It is NOT told that it lacks data, that it may be out of date, or that it should hedge —
 * see cyber-base-instructions.ts. Whatever it does when asked about a 2026 advisory is what
 * an ungrounded agent actually does, which is the entire point of the comparison.
 */
export const cyberBaselineAgent = new Agent({
  id: 'cyber-baseline-agent',
  name: 'Cyber Baseline (no data)',
  instructions: CYBER_BASE_INSTRUCTIONS,
  model: 'openai/gpt-5.6-sol',
});
