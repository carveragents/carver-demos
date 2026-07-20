/**
 * Factory for domain-backed semantic search tools.
 *
 * One vector index per domain, declared in data/carver-domains.json — the same file
 * scripts/build-domain-index.mjs reads, so the index name and DB path cannot drift
 * between the builder and the reader. Adding a domain needs no change to this file.
 *
 * `mastra dev` runs with CWD = src/mastra/public (where its own mastra.db lands), so the
 * relative `file:./<dbFile>` URL resolves to src/mastra/public/<dbFile> — exactly where
 * the build script writes.
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createTool } from '@mastra/core/tools';
import { LibSQLVector } from '@mastra/libsql';
import { z } from 'zod';
import { type RawHit, runEnforcementSearch } from './carver-enforcement-search.ts';
import { embed } from './embed.ts';

const REGISTRY_PATH = join(dirname(fileURLToPath(import.meta.url)), '../../../data/carver-domains.json');
const DEFAULT_LIMIT = 5;

/** A domain entry as declared in data/carver-domains.json. */
export type DomainConfig = {
  id: string;
  dbFile: string;
  indexName: string;
  toolId: string;
  toolName: string;
  label: string;
  description: string;
  queryHint: string;
};

export function loadDomains(path = REGISTRY_PATH): DomainConfig[] {
  return (JSON.parse(readFileSync(path, 'utf8')) as { domains: DomainConfig[] }).domains;
}

export function findDomain(id: string, domains = loadDomains()): DomainConfig {
  const domain = domains.find((d) => d.id === id);
  if (!domain) {
    throw new Error(`Unknown domain "${id}". Known: ${domains.map((d) => d.id).join(', ')}`);
  }
  return domain;
}

const signalSchema = z.object({
  title: z.string(),
  regulator: z.string(),
  date: z.string().describe('Publication date, YYYY-MM-DD'),
  updateType: z.string(),
  whatChanged: z.string(),
  whyItMatters: z.string(),
  keyRequirements: z.array(z.string()),
  impactScore: z.number().nullable(),
  tags: z.array(z.string()),
  sourceUrl: z
    .string()
    .describe(
      'Direct link to the source document on the issuing body\'s own site. Cite this ' +
        'whenever you reference the record, so the reader can verify the claim.',
    ),
  score: z.number().describe('Semantic similarity to the query, higher is closer'),
});

/**
 * Build a `createTool` search tool over one domain's vector index.
 *
 * Opening a not-yet-built store is fine: the query fails, we warn once naming the exact
 * build command for THIS domain, and return no results — so the agent says it found
 * nothing rather than crashing.
 */
export function createDomainSearchTool(domain: DomainConfig) {
  const store = new LibSQLVector({
    id: `carver-${domain.id}-vector`,
    url: `file:./${domain.dbFile}`,
  });
  let warnedNoStore = false;

  const queryVectors = async (vector: number[], topK: number): Promise<RawHit[]> => {
    try {
      return (await store.query({
        indexName: domain.indexName,
        queryVector: vector,
        topK,
      })) as RawHit[];
    } catch (err) {
      if (!warnedNoStore) {
        warnedNoStore = true;
        console.warn(
          `[${domain.toolName}] vector store query failed (${(err as Error).message}). ` +
            `Run: npm run build:domain -- ${domain.id} <path-to-annotations.jsonl>`,
        );
      }
      return [];
    }
  };

  return createTool({
    id: domain.toolId,
    description: domain.description,
    inputSchema: z.object({
      query: z.string().min(1).describe(domain.queryHint),
      limit: z.number().int().positive().optional().describe('Max signals to return (default 5)'),
    }),
    outputSchema: z.object({
      matchCount: z.number().describe('Number of signals returned'),
      signals: z.array(signalSchema),
    }),
    execute: async (inputData) => {
      const hits = await runEnforcementSearch(
        { embed, queryVectors },
        inputData.query,
        inputData.limit ?? DEFAULT_LIMIT,
      );
      return { matchCount: hits.length, signals: hits };
    },
  });
}
