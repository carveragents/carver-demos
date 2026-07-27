import { Agent } from '@mastra/core/agent';
import { ADVISOR_BASE_INSTRUCTIONS, ADVISOR_TRIGGER } from './advisor-base-instructions.ts';
import { searchCarverFull } from '../tools/carver-full-tool.ts';

/**
 * The Carver arm of the cost–accuracy–latency experiment, grounded on the FULL corpus —
 * ~229k records across every sector and regulator — rather than one hand-picked domain slice.
 *
 * This is the arm that matches what the whitepaper actually claims. The per-domain Carver
 * agents (cryptoCarverAgent, deviceCarverAgent, …) each search 1.5k–7k records, about 8% of
 * the corpus between them, and each one is pre-aimed at its scenario's subject matter. Any
 * result from those arms measures "Carver data, pre-filtered to the right sector by a human"
 * — which is not a capability a customer gets. This agent gets the question cold against
 * everything, which is.
 *
 * Same model, same ADVISOR_BASE_INSTRUCTIONS, same verbatim ADVISOR_TRIGGER as the web arm and
 * every domain Carver arm. The tool-intro paragraph names no obligation, deadline, sector, or
 * jurisdiction — if it did, the agent would be reciting the prompt rather than retrieving.
 */
export const fullCarverAgent = new Agent({
  id: 'full-carver-agent',
  name: 'Full-Corpus Carver (grounded)',
  instructions: `${ADVISOR_BASE_INSTRUCTIONS}

You can search Carver's full regulatory corpus with searchCarverFull — records from regulators, supervisory authorities and standards bodies across every sector and jurisdiction Carver covers. Each record carries the issuing body, the date, an extracted list of key requirements, and a sourceUrl. Whenever you rely on a record, include its sourceUrl as a markdown link on the title so the reader can check it. Never invent or adjust a URL. The corpus is large and general, so a first search may return records from an unrelated sector — when that happens, search again with wording closer to the situation rather than reporting an unrelated record.

${ADVISOR_TRIGGER}`,
  model: 'openai/gpt-5.6-sol',
  // Same cap as every other arm — see cryptoCarverAgent for the rationale.
  defaultOptions: { maxSteps: 8 },
  tools: { searchCarverFull },
});
