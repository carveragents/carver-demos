import { Agent } from '@mastra/core/agent';
import { INVESTMENT_BASE_INSTRUCTIONS } from './investment-base-instructions.ts';

/**
 * The control: an investment-education assistant with no tools and no data. Not sandbagged —
 * just ungrounded. It answers reckless questions from model memory alone.
 */
export const investmentBaselineAgent = new Agent({
  id: 'investment-baseline-agent',
  name: 'Investment Baseline (no data)',
  instructions: INVESTMENT_BASE_INSTRUCTIONS,
  model: 'openai/gpt-5.6-sol',
});
