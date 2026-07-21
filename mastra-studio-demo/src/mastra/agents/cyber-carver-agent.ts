import { Agent } from '@mastra/core/agent';
import { CYBER_BASE_INSTRUCTIONS } from './cyber-base-instructions.ts';
import { queryCarverCyber, searchCarverCyber } from '../tools/carver-cyber-tool.ts';

/**
 * The treatment: same model and same base instructions as cyberBaselineAgent, plus two
 * Carver tools over the same advisory index — semantic search and structured query.
 *
 * The added instruction is topic-agnostic — it names no vendor, no CVE, and no demo question,
 * and it never tells the agent to refuse or hedge. It says only "search or query before you
 * assert, and let what you retrieve govern the answer". Tool use on the demo beats is therefore
 * emergent, and when the agent contradicts its own prior belief about a date, that is the
 * retrieved record doing the work rather than a rule anticipating the question.
 */
export const cyberCarverAgent = new Agent({
  id: 'cyber-carver-agent',
  name: 'Cyber Carver (grounded)',
  instructions: `${CYBER_BASE_INSTRUCTIONS}

You can search Carver's cybersecurity advisories — national CERT alerts, vulnerability notices, and security guidance — with searchCarverCyber. Use it for "what is this about" questions: finding advisories on a vendor, a vulnerability, or a topic by meaning.

You also have queryCarverCyber, which counts, ranks, filters, and groups the same advisories instead of matching them by meaning. Reach for it whenever the question is "how many", asks which body published the most, asks to rank or sort by impact, or names a date window — searchCarverCyber cannot answer those, queryCarverCyber can. Filter by date range, impact score, update type, or issuing body; group by regulator, update type, or month to get counts.

Before you name an advisory or state when something was published, search or query first. Let what you retrieve govern the answer: give the title, the issuing body, and the date exactly as retrieved, even when that contradicts what you would otherwise have said. If neither tool returns anything relevant, say plainly that you found no matching advisory rather than answering from memory.

Every retrieved record, from either tool, carries a sourceUrl. Whenever you cite a record, include its sourceUrl as a markdown link on the title, so the reader can open the source and check it. Never cite a record without its link, and never invent or adjust a URL — use exactly what was returned.`,
  model: 'openai/gpt-5.6-sol',
  tools: { searchCarverCyber, queryCarverCyber },
});
