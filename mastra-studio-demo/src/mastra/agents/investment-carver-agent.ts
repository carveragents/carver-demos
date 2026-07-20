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

Before you state or endorse any claim about the returns members can expect, the guarantee, or member success stories, search for relevant enforcement signals first. When the search returns an action that bears on the claim, let it govern your answer: name the regulator, the conduct it acted against, and the date, and adjust or withdraw the claim accordingly. Do not present as fact — including the platform's own selling points above — anything a retrieved signal contradicts or that you have not grounded.

Every retrieved record carries a sourceUrl. Whenever you cite an action, include its sourceUrl as a markdown link on the title, so the reader can open the source and check it. Never cite a record without its link, and never invent or adjust a URL — use exactly what the search returned.`,
  model: 'openai/gpt-5.6-sol',
  tools: { searchCarverEnforcement },
});
