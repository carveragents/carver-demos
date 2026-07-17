import { Agent } from '@mastra/core/agent';
import { searchCarverEnforcement } from '../tools/carver-enforcement-tool.ts';
import { INVESTMENT_BASE_INSTRUCTIONS } from './investment-base-instructions.ts';

/**
 * The treatment: same model and same base instructions as investmentBaselineAgent, plus one
 * enforcement-search tool. The added instruction only governs tool use and is topic-agnostic —
 * it never mentions returns, refunds, or a specific question. Any caution the agent shows is a
 * consequence of what it retrieves, not of a "refuse" rule.
 */
export const investmentCarverAgent = new Agent({
  id: 'investment-carver-agent',
  name: 'Investment Carver (grounded)',
  instructions: `${INVESTMENT_BASE_INSTRUCTIONS}

You can search Carver's regulatory enforcement signals from the FTC, SEC, CFTC, and CFPB with searchCarverEnforcement.

Use it to ground factual claims about what you can promise members, what returns or outcomes to cite, and what regulators have taken action on. When a retrieved signal is relevant, name the regulator and what was penalized, and give the date. Do not state as fact things you have not grounded in a retrieved signal.`,
  model: 'openai/gpt-5.6-sol',
  tools: { searchCarverEnforcement },
});
