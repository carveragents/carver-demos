import { Agent } from '@mastra/core/agent';
import { CYBER_BASE_INSTRUCTIONS } from './cyber-base-instructions.ts';
import { searchCarverCyber } from '../tools/carver-cyber-tool.ts';

/**
 * The treatment: same model and same base instructions as cyberBaselineAgent, plus one
 * advisory-search tool.
 *
 * The added instruction is topic-agnostic — it names no vendor, no CVE, and no demo question,
 * and it never tells the agent to refuse or hedge. It says only "search before you assert,
 * and let what you retrieve govern the answer". Tool use on the demo beats is therefore
 * emergent, and when the agent contradicts its own prior belief about a date, that is the
 * retrieved record doing the work rather than a rule anticipating the question.
 */
export const cyberCarverAgent = new Agent({
  id: 'cyber-carver-agent',
  name: 'Cyber Carver (grounded)',
  instructions: `${CYBER_BASE_INSTRUCTIONS}

You can search Carver's cybersecurity advisories — national CERT alerts, vulnerability notices, and security guidance — with searchCarverCyber.

Before you name an advisory or state when something was published, search first. Let what you retrieve govern the answer: give the title, the issuing body, and the date exactly as retrieved, even when that contradicts what you would otherwise have said. If the search returns nothing relevant, say plainly that you found no matching advisory rather than answering from memory.

Every retrieved record carries a sourceUrl. Whenever you cite a record, include its sourceUrl as a markdown link on the title, so the reader can open the source and check it. Never cite a record without its link, and never invent or adjust a URL — use exactly what the search returned.`,
  model: 'openai/gpt-5.6-sol',
  tools: { searchCarverCyber },
});
