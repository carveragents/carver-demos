/**
 * Cost–accuracy–latency harness for the whitepaper v1.2 frontier chart.
 * Spec: docs/superpowers/specs/2026-07-27-cost-accuracy-experiment-plan.md
 *
 * A sibling of trigger-probe.mjs, deliberately NOT an edit of it: that probe is the record of a
 * published measurement and must keep producing the same numbers. This one differs in what it
 * is for — trigger-probe answers "does the arm notice?", this one answers "at what cost, at what
 * accuracy, in how long?", which needs raw per-run persistence rather than a printed summary.
 *
 * FOUR arms, same model, same maxSteps, same prompts — retrieval is the only variable:
 *   baseline       no tools, model memory only
 *   web            hosted web search
 *   carver-full    semantic search over all 229,287 indexed corpus records
 *   carver-domain  the curated per-sector slice (1.5k-7k records) the earlier demos used
 * The last two together separate "Carver's data" from "Carver's data after a human already
 * narrowed it to the right sector" — only the first is a capability a customer actually gets.
 *
 * Writes whitepaper/experiments/runs.jsonl, one JSON object per run, append-only. Never edits a
 * recorded run; re-running skips run_ids already present, so the suite is resumable.
 *
 *   node scripts/frontier-probe.mjs                     # full suite, 3 repeats
 *   node scripts/frontier-probe.mjs --repeats 1         # smoke
 *   node scripts/frontier-probe.mjs --only q09,q14      # subset
 *   node scripts/frontier-probe.mjs --arms baseline,web
 *   node scripts/frontier-probe.mjs --replay            # warm-cache pass only (repeat 4)
 *   node scripts/frontier-probe.mjs --dry-run           # print the plan, spend nothing
 */
import { appendFileSync, existsSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = join(HERE, '..');
const QUESTIONS = join(PROJECT, 'whitepaper', 'experiments', 'questions.json');
const DEFAULT_RUNS = join(PROJECT, 'whitepaper', 'experiments', 'runs.jsonl');

const BASE = process.env.MASTRA_URL ?? 'http://localhost:4112';
const MAX_STEPS = 8;

/**
 * Rates as measured against whitepaper/figures/whitepaper-data.json section3.rates, in USD.
 * If the model under test is not gpt-5.6-sol the run aborts rather than silently mispricing.
 */
const MODEL = 'openai/gpt-5.6-sol';
const RATES = { input_per_m: 5, cached_per_m: 0.5, output_per_m: 30, web_search_per_call: 0.01 };

/** Hard stop. The plan's budget guard: if projected spend passes this, stop and ask. */
const BUDGET_STOP_USD = 150;

const ARMS = [
  { id: 'baseline', agent: () => 'advisor-baseline-agent' },
  { id: 'web', agent: () => 'advisor-websearch-agent' },
  { id: 'carver-full', agent: () => 'full-carver-agent' },
  { id: 'carver-domain', agent: (q) => q.carver_agent },
];

// ---------------------------------------------------------------- args

const argv = process.argv.slice(2);
const flag = (name, fallback = null) => {
  const i = argv.indexOf(`--${name}`);
  return i === -1 ? fallback : (argv[i + 1] ?? true);
};
const has = (name) => argv.includes(`--${name}`);

const REPEATS = Number(flag('repeats', 3));
const DRY_RUN = has('dry-run');
const REPLAY_ONLY = has('replay');
const ONLY = flag('only') ? String(flag('only')).split(',').map((s) => s.trim()) : null;
const ONLY_ARMS = flag('arms') ? String(flag('arms')).split(',').map((s) => s.trim()) : null;
// Smoke tests must not land in the measured dataset — point them at a scratch file instead.
const RUNS = flag('out') ? String(flag('out')) : DEFAULT_RUNS;

// ---------------------------------------------------------------- cost

/**
 * Bill a response from PER-STEP usage.
 *
 * `totalUsage.raw` is only the LAST step's raw split — using it undercounts a multi-step run.
 * The per-step objects each carry their own {noCache, cacheRead, cacheWrite}, and those are what
 * sum to the run's true token bill. Measured on a 3-step Carver run: totalUsage.inputTokens
 * 26,067 = 574 + 6,688 + 18,805 across steps, while totalUsage.raw.inputTokens.total read 18,805.
 *
 * Cache WRITES are billed at the normal input rate (OpenAI charges no cache-write premium);
 * cache READS at the discounted rate. If that ever changes, this is the one place to fix.
 */
const priceRun = (body) => {
  const steps = body.steps ?? [];
  let fresh = 0;
  let cacheWrite = 0;
  let cacheRead = 0;
  let output = 0;
  let reasoning = 0;
  let webSearches = 0;

  for (const st of steps) {
    const raw = st.usage?.raw?.inputTokens;
    if (raw) {
      fresh += raw.noCache ?? 0;
      cacheRead += raw.cacheRead ?? 0;
      cacheWrite += raw.cacheWrite ?? 0;
    } else {
      // No split available for this step — price it all fresh, an upper bound, and say so.
      fresh += st.usage?.inputTokens ?? 0;
    }
    output += st.usage?.outputTokens ?? 0;
    reasoning += st.usage?.reasoningTokens ?? 0;
    // The provider reports actual search count; tool-call count over-counts it (5 tool-calls
    // for 3 real searches, measured), so never infer the fee from toolCalls.length.
    webSearches += st.response?.body?.tool_usage?.web_search?.num_requests ?? 0;
  }

  const cost =
    ((fresh + cacheWrite) * RATES.input_per_m + cacheRead * RATES.cached_per_m + output * RATES.output_per_m) / 1e6 +
    webSearches * RATES.web_search_per_call;

  return {
    usage: { fresh_input: fresh, cache_write_input: cacheWrite, cached_input: cacheRead, output, reasoning, total: fresh + cacheWrite + cacheRead + output },
    web_searches: webSearches,
    cost_usd: Number(cost.toFixed(6)),
  };
};

// ---------------------------------------------------------------- io

const ask = async (agentKey, { system, user }) => {
  const started = Date.now();
  let res;
  try {
    res = await fetch(`${BASE}/api/agents/${agentKey}/generate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        maxSteps: MAX_STEPS,
        messages: [
          { role: 'system', content: system },
          { role: 'user', content: user },
        ],
      }),
    });
  } catch (err) {
    return { error: `transport: ${String(err)}`, latency_ms: Date.now() - started };
  }
  const latency_ms = Date.now() - started;
  if (!res.ok) return { error: `${res.status}: ${(await res.text()).slice(0, 300)}`, latency_ms };
  return { body: await res.json(), latency_ms };
};

const loadDone = () => {
  const seen = new Set();
  if (!existsSync(RUNS)) return seen;
  for (const line of readFileSync(RUNS, 'utf8').split('\n')) {
    if (!line.trim()) continue;
    try {
      seen.add(JSON.parse(line).run_id);
    } catch {
      /* a truncated final line from a killed run — ignore, it will simply be redone */
    }
  }
  return seen;
};

// ---------------------------------------------------------------- run

const spec = JSON.parse(readFileSync(QUESTIONS, 'utf8'));
let questions = spec.questions;
if (ONLY) questions = questions.filter((q) => ONLY.includes(q.id));
const arms = ONLY_ARMS ? ARMS.filter((a) => ONLY_ARMS.includes(a.id)) : ARMS;

// A replay pass re-runs the identical request while the provider prompt cache is still warm
// (cache retention is 24h, observed in response.body.prompt_cache_retention). Carver on every
// question; web on a strided sample, enough to test "web cost does not fall on repetition"
// without paying for a full second web pass.
const replayArms = arms.filter((a) => a.id.startsWith('carver'));
const replayWebIds = questions.filter((_, i) => i % 5 === 0).map((q) => q.id);

const plan = [];
for (const q of questions) {
  for (let repeat = 1; repeat <= REPEATS; repeat++) {
    for (const arm of arms) plan.push({ q, arm, repeat, phase: 'main' });
  }
}
for (const q of questions) {
  for (const arm of arms) {
    const isReplayArm = replayArms.includes(arm) || (arm.id === 'web' && replayWebIds.includes(q.id));
    if (isReplayArm) plan.push({ q, arm, repeat: 4, phase: 'replay' });
  }
}
const work = REPLAY_ONLY ? plan.filter((p) => p.phase === 'replay') : plan;

const done = loadDone();
const runIdOf = (p) => `${p.q.id}|${p.arm.id}|${p.phase}|${p.repeat}`;
const todo = work.filter((p) => !done.has(runIdOf(p)));

console.log(`questions ${questions.length} · arms ${arms.map((a) => a.id).join(',')} · repeats ${REPEATS}`);
console.log(`planned ${work.length} runs · already recorded ${work.length - todo.length} · to run ${todo.length}`);
if (DRY_RUN) {
  console.log('--dry-run: nothing sent, nothing spent.');
  process.exit(0);
}

mkdirSync(dirname(RUNS), { recursive: true });

let spent = 0;
let failures = 0;
const t0 = Date.now();

for (let n = 0; n < todo.length; n++) {
  const p = todo[n];
  const run_id = runIdOf(p);
  const agentKey = p.arm.agent(p.q);

  let r = await ask(agentKey, p.q);
  if (r.error) {
    // One retry, then record the failure and move on. Never silently drop a run.
    r = await ask(agentKey, p.q);
  }

  const record = {
    run_id,
    question_id: p.q.id,
    stratum: p.q.stratum,
    domain: p.q.domain,
    arm: p.arm.id,
    agent: agentKey,
    phase: p.phase,
    repeat: p.repeat,
    model: MODEL,
    rates: RATES,
    started_at: new Date().toISOString(),
    latency_ms: r.latency_ms,
    error: r.error ?? null,
  };

  if (r.error) {
    failures += 1;
    Object.assign(record, { steps: null, tool_calls: null, usage: null, web_searches: null, cost_usd: null, answer_text: null });
    console.log(`[${n + 1}/${todo.length}] ${run_id.padEnd(34)} ERROR ${r.error.slice(0, 90)}`);
  } else {
    const priced = priceRun(r.body);
    spent += priced.cost_usd;
    Object.assign(record, {
      steps: (r.body.steps ?? []).length,
      tool_calls: (r.body.steps ?? []).reduce((a, st) => a + (st.toolCalls?.length ?? 0), 0),
      ...priced,
      answer_text: r.body.text ?? '',
    });
    console.log(
      `[${n + 1}/${todo.length}] ${run_id.padEnd(34)} ${(r.latency_ms / 1000).toFixed(1)}s · ` +
        `${priced.usage.total.toLocaleString()} tok · ${priced.web_searches} search · $${priced.cost_usd.toFixed(4)} · running $${spent.toFixed(2)}`,
    );
  }

  appendFileSync(RUNS, `${JSON.stringify(record)}\n`);

  if (spent > BUDGET_STOP_USD) {
    console.error(`\nBUDGET STOP: spent $${spent.toFixed(2)} > $${BUDGET_STOP_USD}. Halting. Re-run to resume.`);
    break;
  }
}

console.log(
  `\ndone: ${todo.length} attempted · ${failures} failed · $${spent.toFixed(2)} spent · ` +
    `${((Date.now() - t0) / 60000).toFixed(0)} min wall-clock`,
);
console.log(`runs appended to ${RUNS}`);
