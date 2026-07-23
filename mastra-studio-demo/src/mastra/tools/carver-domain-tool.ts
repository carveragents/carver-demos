/**
 * Factories for domain-backed tools: semantic search (createDomainSearchTool) and
 * structured query (createDomainQueryTool), both over the same per-domain table.
 *
 * One vector index per domain, declared in data/carver-domains.json — the same file
 * scripts/build-domain-index.mjs reads, so the index name and DB path cannot drift
 * between the builder and the reader. Adding a domain needs no change to this file.
 *
 * `mastra dev` runs with CWD = src/mastra/public (where its own mastra.db lands), so the
 * relative `file:./<dbFile>` URL resolves to src/mastra/public/<dbFile> — exactly where
 * the build script writes. Both factories use this identical URL form.
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createClient } from '@libsql/client';
import { createTool } from '@mastra/core/tools';
import { LibSQLVector } from '@mastra/libsql';
import { z } from 'zod';
import { type RawHit, runEnforcementSearch } from './carver-enforcement-search.ts';
import { type DomainRecord, runDomainQuery } from './carver-domain-query.ts';
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
  queryToolId: string;
  queryToolName: string;
  queryDescription: string;
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

/**
 * The fields common to every record, shared by the search tool's signalSchema (below) and
 * the query tool's outputSchema (createDomainQueryTool) — one declaration so the two tools'
 * shapes cannot drift apart.
 */
const domainRecordSchema = z.object({
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
});

const signalSchema = domainRecordSchema.extend({
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

const groupSchema = z.object({
  key: z.string(),
  count: z.number(),
  maxImpact: z.number().nullable(),
});

/**
 * Build a `createTool` structured-query tool over one domain's records: filter, rank, and
 * group-count, the complement to createDomainSearchTool's "what is this about" search.
 *
 * Records are loaded straight from the metadata column (no vector math needed here) and
 * cached in memory on first use — a domain is ~2k rows, so reading the whole table once is
 * cheap and correct, and every later call in the process reuses it. The cache lives in this
 * closure, so it is per-tool: cyber and enforcement each get their own copy.
 *
 * Same degrade-on-missing-index contract as the search factory: a query against a
 * not-yet-built table throws, we warn once naming the exact build command for THIS domain,
 * cache an empty array (so we don't retry and re-warn every call), and return zero matches.
 */
export function createDomainQueryTool(domain: DomainConfig) {
  let cache: DomainRecord[] | null = null;
  let warnedNoStore = false;

  const loadRecords = async (): Promise<DomainRecord[]> => {
    if (cache) return cache;
    try {
      const client = createClient({ url: `file:./${domain.dbFile}` });
      const result = await client.execute(`SELECT metadata FROM ${domain.indexName}`);
      cache = result.rows.map((row) => JSON.parse(row.metadata as string) as DomainRecord);
    } catch (err) {
      if (!warnedNoStore) {
        warnedNoStore = true;
        console.warn(
          `[${domain.queryToolName}] structured query failed (${(err as Error).message}). ` +
            `Run: npm run build:domain -- ${domain.id} <path-to-annotations.jsonl>`,
        );
      }
      cache = [];
    }
    return cache;
  };

  return createTool({
    id: domain.queryToolId,
    description: domain.queryDescription,
    inputSchema: z.object({
      dateFrom: z.string().optional().describe('YYYY-MM-DD, inclusive'),
      dateTo: z.string().optional().describe('YYYY-MM-DD, inclusive'),
      minImpact: z.number().min(0).max(10).optional().describe('Minimum impact score, 0-10 inclusive'),
      updateType: z.string().optional().describe('Exact update type to match, case-insensitive'),
      regulator: z
        .string()
        .optional()
        .describe('Substring to match against the issuing body/regulator name, case-insensitive'),
      keyword: z
        .string()
        .optional()
        .describe('Substring to match against the title, what-changed, why-it-matters, and tags, case-insensitive'),
      groupBy: z
        .enum(['regulator', 'updateType', 'month'])
        .optional()
        .describe('Roll matching records up into counts by this axis instead of returning individual records'),
      orderBy: z
        .enum(['date', 'impactScore'])
        .optional()
        .describe('Sort individual records by this field, most recent/highest first (ignored when groupBy is set)'),
      limit: z
        .number()
        .int()
        .positive()
        .optional()
        .describe('Max records to return when not grouping (default 20, max 100)'),
    }),
    outputSchema: z.object({
      matchCount: z.number().describe('Total records matching the filters, before limit is applied'),
      records: z.array(domainRecordSchema),
      groups: z.array(groupSchema),
    }),
    execute: async (inputData) => runDomainQuery(await loadRecords(), inputData),
  });
}
