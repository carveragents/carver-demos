import { Agent } from '@mastra/core/agent';
import { ADVISOR_BASE_INSTRUCTIONS, ADVISOR_TRIGGER } from './advisor-base-instructions.ts';
import { searchCarverDevices } from '../tools/carver-devices-tool.ts';

/**
 * The treatment for the medical-device scenario. Same model, same base instructions, same
 * verbatim trigger clause (ADVISOR_TRIGGER) as advisorWebsearchAgent — only the corpus differs.
 * Search-only; see cryptoCarverAgent for the rationale.
 */
export const deviceCarverAgent = new Agent({
  id: 'device-carver-agent',
  name: 'Device Carver (grounded)',
  instructions: `${ADVISOR_BASE_INSTRUCTIONS}

You can search Carver's medical-device and IVD regulatory signals — registration, UDI, conformity and market-placement records from bodies such as Swissmedic, BfArM, the FDA, the TGA and national competent authorities — with searchCarverDevices. Each record carries the issuing body, the date, an extracted list of key requirements, and a sourceUrl. Whenever you rely on a record, include its sourceUrl as a markdown link on the title so the reader can check it. Never invent or adjust a URL.

${ADVISOR_TRIGGER}`,
  model: 'openai/gpt-5.6-sol',
  // Cap the retrieval loop so the interactive Studio demo cannot thrash — see cryptoCarverAgent.
  defaultOptions: { maxSteps: 8 },
  tools: { searchCarverDevices },
});
