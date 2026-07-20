/**
 * Pure retrieval logic for the enforcement tool: shape vector-store hits into the payload the
 * agent sees, and orchestrate embed -> query -> shape through injected dependencies so it can
 * be unit-tested with no network and no store.
 *
 * Spec: docs/superpowers/specs/2026-07-17-investment-advice-contrast-demo-design.md
 */

/** One enforcement annotation, as stored in the vector DB and returned to the agent. */
export type EnforcementRecord = {
  title: string;
  regulator: string;
  date: string;
  updateType: string;
  whatChanged: string;
  whyItMatters: string;
  keyRequirements: string[];
  impactScore: number | null;
  tags: string[];
  sourceUrl: string;
};

/** A raw hit from the vector store (LibSQLVector QueryResult, minimally typed). */
export type RawHit = {
  id: string;
  score: number;
  metadata?: Record<string, unknown>;
};

/** An enforcement record plus its similarity score, as the agent receives it. */
export type EnforcementHit = EnforcementRecord & { score: number };

/** Injected I/O, so runEnforcementSearch stays unit-testable. */
export type EnforcementDeps = {
  embed: (text: string) => Promise<number[]>;
  queryVectors: (vector: number[], topK: number) => Promise<RawHit[]>;
};

const EMPTY_RECORD: EnforcementRecord = {
  title: '',
  regulator: '',
  date: '',
  updateType: '',
  whatChanged: '',
  whyItMatters: '',
  keyRequirements: [],
  impactScore: null,
  tags: [],
  sourceUrl: '',
};

const toRecord = (metadata: Record<string, unknown> = {}): EnforcementRecord =>
  ({ ...EMPTY_RECORD, ...metadata }) as EnforcementRecord;

/**
 * Shape raw store hits into the agent payload: most similar first, below-threshold dropped,
 * truncated to limit. Pure.
 */
export function shapeHits(hits: RawHit[], limit: number, minScore = 0): EnforcementHit[] {
  return hits
    .filter((hit) => hit.score >= minScore)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((hit) => ({ ...toRecord(hit.metadata), score: hit.score }));
}

/** Embed the query, ask the store for the nearest records, shape them. */
export async function runEnforcementSearch(
  deps: EnforcementDeps,
  query: string,
  limit: number,
  minScore = 0,
): Promise<EnforcementHit[]> {
  const vector = await deps.embed(query);
  const hits = await deps.queryVectors(vector, limit);
  return shapeHits(hits, limit, minScore);
}
