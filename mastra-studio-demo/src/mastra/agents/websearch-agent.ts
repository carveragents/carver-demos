import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { BASE_INSTRUCTIONS } from './base-instructions.ts';

/**
 * Scenario 1's third arm — the same control `cyber-websearch-agent` provides for scenario 3,
 * and for the same reason: without it, any claim that the grounded column needs *Carver*
 * rather than merely *grounding* is untested. In scenario 3 that control overturned the
 * argument (see docs/DEMO.md). Assume it can here too until measured.
 *
 * Same model and the same `BASE_INSTRUCTIONS` as baseline-agent and carver-agent, so the only
 * variable is where the data comes from.
 *
 * The two constraints from `cyber-websearch-agent` apply here unchanged and are load-bearing:
 * this agent must never be given a Carver tool (`@mastra/core` silently drops function tools
 * when mixed with provider-defined ones — a warning, not an error, so a combined agent would
 * look fine and retrieve nothing), and the `@ai-sdk/openai` import is the deliberate exception
 * to the no-`@ai-sdk/*` rule, which is about model routing, not provider-defined tools.
 */
export const websearchAgent = new Agent({
  id: 'websearch-agent',
  name: 'Web Search (no Carver)',
  instructions: `${BASE_INSTRUCTIONS}

You can search the live web with webSearch.

Before you state what a body has published or when, search the web first, and prefer the body's
own site over secondary coverage. Give the title and the date as published, and link to the page
you used. If you cannot find it, say so plainly rather than answering from memory.`,
  model: 'openai/gpt-5.6-sol',
  tools: {
    webSearch: openai.tools.webSearch(),
  },
});
