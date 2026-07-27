/**
 * Search tool over the FULL Carver corpus — every sector, every regulator, ~229k records —
 * rather than one of the curated per-domain slices in carver-domain-tool.ts.
 *
 * Why this file exists instead of reusing createDomainSearchTool: scale changes the access
 * path. LibSQLVector's `store.query()` brute-forces vector_distance_cos across the whole table,
 * which measures 2,622 ms at 7,146 rows and extrapolates to ~90 s at 229k — unusable inside an
 * agent loop. The full index therefore carries a compressed DiskANN index (built by
 * scripts/build-domain-index.mjs above ANN_THRESHOLD), and the ONLY way to hit it is
 * `vector_top_k(...)`. Measured on the same data: 161 ms end-to-end including the metadata join.
 *
 * Everything downstream of retrieval — hit shaping, the record schema the agent sees — is the
 * shared logic from carver-enforcement-search.ts, so full-corpus hits and domain hits are the
 * same shape and the two arms differ only in what they searched.
 */
import { createClient } from '@libsql/client';
import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { type RawHit, runEnforcementSearch } from './carver-enforcement-search.ts';
import { findDomain } from './carver-domain-tool.ts';
import { embed } from './embed.ts';

const DEFAULT_LIMIT = 5;

const recordSchema = z.object({
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
      "Direct link to the source document on the issuing body's own site. Cite this whenever " +
        'you reference the record, so the reader can verify the claim.',
    ),
  score: z.number().describe('Semantic similarity to the query, higher is closer'),
});

/** Build the full-corpus search tool. Same contract as createDomainSearchTool, ANN access path. */
export function createFullCorpusSearchTool() {
  const domain = findDomain('full');
  const client = createClient({ url: `file:./${domain.dbFile}` });
  const annIndex = `${domain.indexName}_ann`;
  let warned = false;

  const queryVectors = async (vector: number[], topK: number): Promise<RawHit[]> => {
    const literal = JSON.stringify(vector);
    try {
      const res = await client.execute({
        // vector_top_k walks the compressed DiskANN index and returns rowids; the join pulls
        // the metadata back. Score is recomputed exactly on the (few) returned rows, so the
        // ranking the agent sees is a true cosine similarity, not an ANN approximation of one.
        sql:
          `SELECT f.rowid AS id, ` +
          `1 - vector_distance_cos(f.embedding, vector32(?)) AS score, ` +
          `f.metadata AS metadata ` +
          `FROM vector_top_k('${annIndex}', vector32(?), ?) AS v ` +
          `JOIN ${domain.indexName} AS f ON f.rowid = v.id ` +
          `ORDER BY score DESC`,
        args: [literal, literal, topK],
      });
      return res.rows.map((row) => ({
        id: String(row.id),
        score: Number(row.score),
        metadata: JSON.parse(String(row.metadata ?? '{}')),
      }));
    } catch (err) {
      if (!warned) {
        warned = true;
        console.warn(
          `[${domain.toolName}] full-corpus query failed (${(err as Error).message}). ` +
            `Run: npm run build:domain -- full <path-to-annotations.jsonl>`,
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
      limit: z.number().int().positive().optional().describe('Max records to return (default 5)'),
    }),
    outputSchema: z.object({
      matchCount: z.number().describe('Number of records returned'),
      signals: z.array(recordSchema),
    }),
    execute: async (inputData) => {
      const hits = await runEnforcementSearch({ embed, queryVectors }, inputData.query, inputData.limit ?? DEFAULT_LIMIT);
      return { matchCount: hits.length, signals: hits };
    },
  });
}

export const searchCarverFull = createFullCorpusSearchTool();
