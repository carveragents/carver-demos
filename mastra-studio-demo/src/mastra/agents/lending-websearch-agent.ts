import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { LENDING_BASE_INSTRUCTIONS } from './lending-base-instructions.ts';

/**
 * The arm that decides whether this demo is about *Carver* or merely about *grounding*.
 * In scenario 3 the equivalent control overturned the argument (see docs/DEMO.md), so it
 * exists here from the start rather than being added after a favourable result.
 *
 * Its search-trigger clause is worded identically to `lending-carver-agent`'s — same trigger
 * conditions, same obligations, only the tool differs. If the wording drifts apart, any gap
 * we measure could be prompt phrasing rather than data.
 *
 * Never give this agent a Carver tool: `@mastra/core` silently drops function tools when they
 * are mixed with provider-defined ones, so a combined agent would look healthy and retrieve
 * nothing. The `@ai-sdk/openai` import is the deliberate exception to the no-`@ai-sdk/*` rule,
 * which governs model routing, not provider-defined tools.
 */
export const lendingWebsearchAgent = new Agent({
  id: 'lending-websearch-agent',
  name: 'Lending Web Search (no Carver)',
  instructions: `${LENDING_BASE_INSTRUCTIONS}

You can search the live web with webSearch.

Before you communicate a credit decision, state what the company is required to do, or tell someone what they are entitled to, search first and let what you find govern your answer. Prefer the issuing body's own site over secondary coverage.

Whenever you rely on a source, link to the page you used so the reader can check it. Never invent or adjust a URL. If you cannot find something, say so plainly rather than answering from memory.`,
  model: 'openai/gpt-5.6-sol',
  tools: {
    webSearch: openai.tools.webSearch(),
  },
});
