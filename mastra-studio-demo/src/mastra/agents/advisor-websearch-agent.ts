import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { ADVISOR_BASE_INSTRUCTIONS, ADVISOR_TRIGGER } from './advisor-base-instructions.ts';

/**
 * The arm that decides whether the mini-suite is about *Carver* or merely about *grounding*.
 * It has live web search, so on any well-covered obligation it can reach the same public
 * documents Carver holds. Its edge, if Carver has one, must therefore come from either the
 * trigger failing here (it never realises a rule exists to search for) or from the obligation
 * living in a source web search cannot surface — not from Carver simply "having data".
 *
 * Its trigger clause (ADVISOR_TRIGGER) is worded identically to every Carver arm's. Only the
 * retrieval tool differs. Shared across all three domains.
 *
 * Never give this agent a Carver tool: `@mastra/core` silently drops function tools when they
 * are mixed with provider-defined ones, so a combined agent would look healthy and retrieve
 * nothing. The `@ai-sdk/openai` import is the deliberate exception to the no-`@ai-sdk/*` rule,
 * which governs model routing, not provider-defined tools.
 */
export const advisorWebsearchAgent = new Agent({
  id: 'advisor-websearch-agent',
  name: 'Advisor Web Search (no Carver)',
  instructions: `${ADVISOR_BASE_INSTRUCTIONS}

You can search the live web with webSearch. Prefer the issuing body's own site over secondary coverage, and link to the page you used so the reader can check it. Never invent or adjust a URL.

${ADVISOR_TRIGGER}`,
  model: 'openai/gpt-5.6-sol',
  tools: {
    webSearch: openai.tools.webSearch(),
  },
});
