/**
 * Pure logic for the structured (relational) half of a domain: filter, rank, and
 * group-count over the records already stored in the domain's vector table.
 *
 * This is what web search structurally cannot offer an agent: there is no
 * `minImpact` parameter on the open web. Semantic search answers "what is this
 * about?"; this module answers "how many, which body, ranked by what".
 *
 * Filtering happens in JS over the full record list, not in SQL. A domain holds
 * ~2k records (~2 MB of metadata), so a scan is instant, and plain functions over
 * arrays are testable with fixtures — same trade the searchUpdates matcher makes.
 */

/** The trimmed record shape build-domain-index.mjs stores as row metadata. */
export type DomainRecord = {
  title: string;
  date: string;
  updateType: string;
  regulator: string;
  whatChanged: string;
  whyItMatters: string;
  keyRequirements: string[];
  impactScore: number | null;
  tags: string[];
  sourceUrl: string;
};

export type DomainQuery = {
  dateFrom?: string;
  dateTo?: string;
  minImpact?: number;
  updateType?: string;
  regulator?: string;
  keyword?: string;
  groupBy?: 'regulator' | 'updateType' | 'month';
  orderBy?: 'date' | 'impactScore';
  limit?: number;
};

export type DomainGroup = {
  key: string;
  count: number;
  maxImpact: number | null;
};

export type DomainQueryResult = {
  matchCount: number;
  records: DomainRecord[];
  groups: DomainGroup[];
};

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 100;

const contains = (haystack: string, needle: string) =>
  haystack.toLowerCase().includes(needle.toLowerCase());

const keywordText = (r: DomainRecord) =>
  [r.title, r.whatChanged, r.whyItMatters, r.tags.join(' ')].join('\n');

const matches = (r: DomainRecord, q: DomainQuery): boolean => {
  if (q.dateFrom && r.date < q.dateFrom) return false;
  if (q.dateTo && r.date > q.dateTo) return false;
  if (q.minImpact !== undefined && (r.impactScore === null || r.impactScore < q.minImpact)) return false;
  if (q.updateType && r.updateType.toLowerCase() !== q.updateType.toLowerCase()) return false;
  if (q.regulator && !contains(r.regulator, q.regulator)) return false;
  if (q.keyword && !contains(keywordText(r), q.keyword)) return false;
  return true;
};

/** Dates are ISO strings, so string comparison IS chronological comparison. */
const byDateDesc = (a: DomainRecord, b: DomainRecord) => b.date.localeCompare(a.date);

/** Highest impact first; records without a score sort last, then by date. */
const byImpactDesc = (a: DomainRecord, b: DomainRecord) =>
  (b.impactScore ?? -1) - (a.impactScore ?? -1) || byDateDesc(a, b);

const groupKeyOf = (r: DomainRecord, groupBy: NonNullable<DomainQuery['groupBy']>): string => {
  if (groupBy === 'regulator') return r.regulator;
  if (groupBy === 'updateType') return r.updateType;
  return r.date.slice(0, 7); // month: YYYY-MM
};

const groupRecords = (records: DomainRecord[], groupBy: NonNullable<DomainQuery['groupBy']>): DomainGroup[] => {
  const groups = new Map<string, DomainGroup>();
  for (const r of records) {
    const key = groupKeyOf(r, groupBy) || '(unknown)';
    const group = groups.get(key) ?? { key, count: 0, maxImpact: null };
    group.count += 1;
    if (r.impactScore !== null && r.impactScore > (group.maxImpact ?? -1)) {
      group.maxImpact = r.impactScore;
    }
    groups.set(key, group);
  }
  return [...groups.values()].sort((a, b) => b.count - a.count || a.key.localeCompare(b.key));
};

/**
 * Run a structured query. `matchCount` is always the true total after filtering;
 * `records` is truncated to the limit. When `groupBy` is set, the counts are the
 * answer: `groups` is filled and `records` stays empty.
 */
export function runDomainQuery(records: DomainRecord[], query: DomainQuery): DomainQueryResult {
  const filtered = records.filter((r) => matches(r, query));

  if (query.groupBy) {
    return { matchCount: filtered.length, records: [], groups: groupRecords(filtered, query.groupBy) };
  }

  const limit = Math.min(Math.max(query.limit ?? DEFAULT_LIMIT, 1), MAX_LIMIT);
  const sorted = [...filtered].sort(query.orderBy === 'impactScore' ? byImpactDesc : byDateDesc);
  return { matchCount: filtered.length, records: sorted.slice(0, limit), groups: [] };
}
