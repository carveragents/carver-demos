import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { CYBER_BASE_INSTRUCTIONS } from './cyber-base-instructions.ts';

/**
 * The third arm of scenario 3, and the honest control for the obvious objection:
 * *"why not just give it web search?"*
 *
 * Same model and the same base instructions as the other two — the only difference is that
 * this one can search the live web instead of Carver's corpus. If it closes the gap, that is
 * a real finding about where the value actually sits, and better learned here than on stage.
 *
 * TWO CONSTRAINTS, both load-bearing:
 *
 * 1. **This agent must never be given a Carver tool.** `@mastra/core` refuses to mix function
 *    tools with provider-defined ones: "Cannot mix function tools with provider-defined tools
 *    in the same request. Falling back to provider-defined tools only. The following function
 *    tools will be ignored". It is a WARNING, not an error — a combined agent would look fine
 *    and silently lose its Carver retrieval. A both-sources agent needs a custom function tool
 *    over a search API instead, not this native one.
 *
 * 2. **This is the one place `@ai-sdk/*` is imported on purpose.** README's standing rule is
 *    that no `@ai-sdk/*` package is installed or imported — that rule is about MODEL routing,
 *    where the router string is the whole point. A provider-defined tool has no router-string
 *    form, so the package is a real dependency here and is declared in package.json.
 *    Do not take this as licence to import `@ai-sdk/openai` for models.
 */
export const cyberWebsearchAgent = new Agent({
  id: 'cyber-websearch-agent',
  name: 'Cyber Web Search (no Carver)',
  instructions: `${CYBER_BASE_INSTRUCTIONS}

You can search the live web with webSearch.

Before you name an advisory or state when something was published, search the web first, and prefer the issuing body's own site over secondary coverage. Give the title, the issuing body, and the date as published, and link to the page you used so the reader can check it. If you cannot find a matching advisory, say so plainly rather than answering from memory.`,
  model: 'openai/gpt-5.6-sol',
  tools: {
    webSearch: openai.tools.webSearch(),
  },
});
