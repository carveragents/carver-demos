import { Agent } from '@mastra/core/agent';
import { ADVISOR_BASE_INSTRUCTIONS, ADVISOR_TRIGGER } from './advisor-base-instructions.ts';
import { searchCarverCrypto } from '../tools/carver-crypto-tool.ts';

/**
 * The treatment for the crypto-asset scenario: same model, same base instructions, and the
 * same verbatim trigger clause (ADVISOR_TRIGGER) as advisorWebsearchAgent — only the corpus
 * differs. Search-only, no query tool: these scenarios are about whether an obligation is
 * noticed at all, and the extra tool invites the multi-hundred-call thrashing documented in
 * docs/DEMO.md.
 *
 * The tool-intro paragraph names no obligation, no deadline, and no demo question — if it did,
 * the agent would be reciting the prompt rather than retrieving.
 */
export const cryptoCarverAgent = new Agent({
  id: 'crypto-carver-agent',
  name: 'Crypto Carver (grounded)',
  instructions: `${ADVISOR_BASE_INSTRUCTIONS}

You can search Carver's crypto-asset regulatory signals — licensing, authorisation, and market-conduct records from bodies such as the AMF, BaFin, CNMV, ESMA, CONSOB and the FCA — with searchCarverCrypto. Each record carries the issuing body, the date, an extracted list of key requirements, and a sourceUrl. Whenever you rely on a record, include its sourceUrl as a markdown link on the title so the reader can check it. Never invent or adjust a URL.

${ADVISOR_TRIGGER}`,
  model: 'openai/gpt-5.6-sol',
  // Cap the retrieval loop so the interactive Studio demo cannot thrash. docs/DEMO.md records
  // a prior incident of 200+ searchCarver* calls returning an empty answer; the operational
  // probe applies the same cap per-call, and this makes the live agent safe too. 8 steps is
  // ample for a few refining searches plus the answer (measured), far below any thrash.
  defaultOptions: { maxSteps: 8 },
  tools: { searchCarverCrypto },
});
