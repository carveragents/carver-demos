import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** One Carver regulatory topic, classified. See scripts/build-topics.mjs. */
export type TopicRecord = {
  topicId: string;
  name: string;
  acronym: string;
  jurisdiction: string;
  system: string;
  sector: string;
  industry: string;
  subIndustry: string;
  confidence: string;
};

export type SearchResult = {
  matchCount: number;
  matches: TopicRecord[];
};

const DATA_PATH = join(dirname(fileURLToPath(import.meta.url)), '../../../data/carver-topics.json');

export function loadTopics(path: string = DATA_PATH): TopicRecord[] {
  return JSON.parse(readFileSync(path, 'utf8')) as TopicRecord[];
}

/**
 * Match tiers, best first. Ranking is what keeps an exact "SEC" acronym hit above the
 * dozen records that merely contain the word "Securities".
 *
 * The last tier is the mirror of the one above it: the query containing the name, rather
 * than the name containing the query. Agents pass through however the user phrased it, and
 * "UK Financial Conduct Authority" is more specific than the stored "Financial Conduct
 * Authority" — without this the lookup reports a false absence, which is worse than a wrong
 * answer for a tool whose whole promise is admitting what it doesn't have. It sits last so
 * it can only answer when every more precise tier is empty.
 */
const TIERS: ((record: TopicRecord, query: string) => boolean)[] = [
  (r, q) => r.acronym.toLowerCase() === q,
  (r, q) => r.name.toLowerCase() === q,
  (r, q) => r.name.toLowerCase().startsWith(q),
  (r, q) => r.name.toLowerCase().includes(q),
  (r, q) => q.includes(r.name.toLowerCase()),
];

const tierOf = (record: TopicRecord, query: string): number =>
  TIERS.findIndex((matches) => matches(record, query));

/**
 * Best-tier-wins: the most precise tier that produces any match is the whole answer.
 * Searching "SEC" yields the 5 bodies whose acronym is exactly SEC — not those 5 plus the
 * 14 records that merely contain "Securities". A lower tier only answers when every tier
 * above it is empty.
 */
export function searchTopics(records: TopicRecord[], query: string, limit = 5): SearchResult {
  const q = query.trim().toLowerCase();
  if (!q) return { matchCount: 0, matches: [] };

  for (const matchesTier of TIERS) {
    const hits = records.filter((record) => matchesTier(record, q));
    if (hits.length > 0) {
      return { matchCount: hits.length, matches: hits.slice(0, limit) };
    }
  }

  return { matchCount: 0, matches: [] };
}
