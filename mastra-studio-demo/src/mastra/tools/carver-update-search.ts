import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { type TopicRecord, searchTopics } from './carver-topic-search.ts';

/** One annotated regulatory document. See scripts/build-updates.mjs. */
export type UpdateRecord = {
  topicId: string;
  title: string;
  date: string;
  updateType: string;
  regulator: string;
  country: string;
  impact: string;
  impactScore: number | null;
  urgency: string;
  whatChanged: string;
  whyItMatters: string;
  keyRequirements: string[];
  tags: string[];
  /** Direct link to the source document on the regulator's own site. */
  sourceUrl: string;
};

/** The regulators a query resolved to, reported when more than one matched. */
export type RegulatorRef = {
  name: string;
  acronym: string;
  jurisdiction: string;
};

export type UpdateSearchResult = {
  matchCount: number;
  ambiguousRegulators: RegulatorRef[];
  updates: UpdateRecord[];
};

export type UpdateQuery = {
  regulator: string;
  keyword?: string;
  limit?: number;
};

const DATA_PATH = join(dirname(fileURLToPath(import.meta.url)), '../../../data/carver-updates.json');

export function loadUpdates(path: string = DATA_PATH): UpdateRecord[] {
  return JSON.parse(readFileSync(path, 'utf8')) as UpdateRecord[];
}

/** Keyword surface: what a human would expect "anything on crypto?" to search. */
const mentions = (update: UpdateRecord, keyword: string): boolean =>
  update.title.toLowerCase().includes(keyword) ||
  update.whatChanged.toLowerCase().includes(keyword) ||
  update.tags.some((tag) => tag.toLowerCase().includes(keyword));

const byDateDesc = (a: UpdateRecord, b: UpdateRecord): number => b.date.localeCompare(a.date);

const EMPTY: UpdateSearchResult = { matchCount: 0, ambiguousRegulators: [], updates: [] };

/**
 * Find what a regulator published, most recent first.
 *
 * Name resolution delegates to searchTopics rather than re-matching here, so acronym
 * handling and best-tier-wins ranking stay identical across both Carver tools. That also
 * means ambiguity is inherited: "SEC" resolves to every SEC, and this reports all of them
 * instead of silently choosing one jurisdiction's updates.
 */
export function searchUpdates(
  topics: TopicRecord[],
  updates: UpdateRecord[],
  { regulator, keyword, limit = 5 }: UpdateQuery,
): UpdateSearchResult {
  const resolved = searchTopics(topics, regulator, topics.length);
  if (resolved.matchCount === 0) return EMPTY;

  const topicIds = new Set(resolved.matches.map((topic) => topic.topicId));
  const needle = keyword?.trim().toLowerCase();

  const hits = updates
    .filter((update) => topicIds.has(update.topicId))
    .filter((update) => !needle || mentions(update, needle))
    .sort(byDateDesc);

  // Only a genuine cross-jurisdiction collision is worth the agent's attention.
  const ambiguousRegulators =
    resolved.matches.length > 1
      ? resolved.matches.map(({ name, acronym, jurisdiction }) => ({ name, acronym, jurisdiction }))
      : [];

  return {
    matchCount: hits.length,
    ambiguousRegulators,
    updates: hits.slice(0, limit),
  };
}
