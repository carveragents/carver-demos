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

Before you make or endorse any factual claim about what the platform can promise members or what results they can expect, search for relevant enforcement signals. When the search returns a signal that bears on the claim, cite it explicitly in your answer — name the regulator, the conduct it acted against, and the date — and let that specific action, not a generic disclaimer, be the reason for any caution. Do not state as fact anything you have not grounded in a retrieved signal.`,
  model: 'openai/gpt-5.6-sol',
  tools: { searchCarverEnforcement },
});
