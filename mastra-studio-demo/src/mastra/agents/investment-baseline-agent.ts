import { Agent } from '@mastra/core/agent';
import { INVESTMENT_BASE_INSTRUCTIONS } from './investment-base-instructions.ts';

/**
 * The control: the enthusiastic sales persona (INVESTMENT_BASE_INSTRUCTIONS) with no tools and
 * no enforcement data. Under the same permissive marketing policy as the Carver agent, it
 * answers from model memory alone — so it acts on the persona's pressure to over-commit with
 * nothing to restrain it.
 */
export const investmentBaselineAgent = new Agent({
  id: 'investment-baseline-agent',
  name: 'Investment Baseline (no data)',
  instructions: INVESTMENT_BASE_INSTRUCTIONS,
  model: 'openai/gpt-5.6-sol',
});
