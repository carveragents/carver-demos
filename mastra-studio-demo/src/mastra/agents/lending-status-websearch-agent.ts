import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { LENDING_STATUS_BASE_INSTRUCTIONS, ADVISOR_TRIGGER } from './lending-status-instructions.ts';
import { lookupApplicant } from '../tools/lookup-applicant-tool.ts';

/**
 * The real bar: live web search. Same base + verbatim trigger as the Carver arm; only the grounding
 * tool differs.
 *
 * HAZARD (see docs/continuing.md): @mastra/core can silently drop function tools when they are mixed
 * with a provider-defined tool (webSearch). If lookupApplicant is dropped, this arm cannot pull the
 * applicant file and the lookup flow breaks for the web arm only — verified before shipping; if it
 * drops, web search is wrapped as a function tool instead.
 */
export const lendingStatusWebsearchAgent = new Agent({
  id: 'lending-status-websearch-agent',
  name: 'Lending Status — Web Search (no Carver)',
  instructions: `${LENDING_STATUS_BASE_INSTRUCTIONS}

You can search the live web with webSearch. Prefer the issuing body's own site over secondary coverage, and link to the page you used so the reader can check it. Never invent or adjust a URL.

${ADVISOR_TRIGGER}`,
  model: 'openai/gpt-5.6-sol',
  tools: {
    lookupApplicant,
    webSearch: openai.tools.webSearch(),
  },
});
