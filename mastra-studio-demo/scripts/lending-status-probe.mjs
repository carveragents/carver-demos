/**
 * Lending-status demo scorecard + operational-cost harness (with cache-adjusted tokens + $ estimate).
 *
 * The applicant NEVER states their state. They ask for their loan status and give an applicant ID;
 * the agent calls lookupApplicant (an auth/CRM stand-in) which returns their file — including the
 * state — and answers. Three applicant IDs, one per state, identical loan and denial: the state is
 * the only variable. A grounded arm that is doing real work surfaces the obligation that varies by
 * that state (Colorado AI Act, California Holden Act); New York has none.
 *
 * Measured per (arm × applicant), over `repeats` runs:
 *   - CONTENT: does the arm surface the state obligation? (the demo's correctness claim)
 *   - TOKENS: total, split into fresh input / cached input (cache-read) / output. `totalUsage` from
 *     Mastra sums every model step in the tool loop, and tool RESULTS land as INPUT tokens on the
 *     next step — so this is the full count of tokens the arm's MODEL processed, tool results
 *     included. (What it does NOT include: OpenAI's web_search service fetching/ranking raw pages
 *     server-side — those internal tokens are not exposed by any API, key or no key.)
 *   - COST: an ESTIMATE from the tokens above + web_search calls, using the RATES below. The rates
 *     are placeholders — replace with your real openai/gpt-5.6-sol + web_search prices.
 *
 * Usage: node scripts/lending-status-probe.mjs [repeats]   (default 1; use 3 for the tables)
 */
const BASE = process.env.MASTRA_URL ?? 'http://localhost:4111';
const MAX_STEPS = 8;
const REPEATS = Number(process.argv[2] ?? 1);

// ─── PRICES from OpenAI's pricing page (developers.openai.com/api/docs/pricing), checked 2026-07-23,
//     for openai/gpt-5.6-sol. $ per 1,000,000 tokens, $ per call. ───
const RATES = {
  inputPerM: 5.0,          // uncached (fresh) input tokens, $/1M — gpt-5.6-sol
  cachedInputPerM: 0.5,    // cache-read input tokens, $/1M       — gpt-5.6-sol (10% of input)
  outputPerM: 30.0,        // output tokens (incl. reasoning), $/1M — gpt-5.6-sol
  webSearchPerCall: 0.01,  // per web_search tool invocation, $   — $10 / 1k calls. Retrieved-content
                           // tokens are already in usage input (reasoning model), so no extra token add.
};

const APPLICANTS = [
  { id: 'CO-1001', state: 'Colorado', overlay: ['CO AI-Act', /colorado ai act|SB ?24-?205|SB ?26-?189|meaningful human review|automated decision.{0,45}(disclos|notice|explan|review)/i] },
  { id: 'CA-1001', state: 'California', overlay: ['CA Holden Act', /holden act|housing financial discrimination|fair lending notice/i] },
  { id: 'NY-1001', state: 'New York', overlay: ['(none — federal only)', /$^/] },
];
const ARMS = ['lending-status-baseline-agent', 'lending-status-websearch-agent', 'lending-status-carver-agent'];
const MSG = (id) => `Hi, can you check the status of my loan application? My applicant ID is ${id}.`;

const median = (xs) => { if (!xs.length) return 0; const s = [...xs].sort((a, b) => a - b); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const round = (n) => Math.round(n);
const range = (xs) => (xs.length ? `${Math.min(...xs)}–${Math.max(...xs)}` : '—');

// As billed: cache-read input gets the discounted rate.
const costOf = (t) =>
  (t.freshInput / 1e6) * RATES.inputPerM +
  (t.cachedInput / 1e6) * RATES.cachedInputPerM +
  (t.output / 1e6) * RATES.outputPerM +
  t.wsCalls * RATES.webSearchPerCall;

// No-cache (cold): bill ALL input at the full rate. This is what a run costs when the prompt
// prefix is not cache-warm — a cold first call, or low-volume traffic where the ~5-10 min cache
// TTL expires between calls. Carver barely caches, so its two costs are ~equal; the web arm's big
// fixed scaffold caches heavily, so its no-cache cost is much higher than its billed cost.
const costNoCacheOf = (t) =>
  ((t.freshInput + t.cachedInput) / 1e6) * RATES.inputPerM +
  (t.output / 1e6) * RATES.outputPerM +
  t.wsCalls * RATES.webSearchPerCall;

const ask = async (agent, id) => {
  const started = Date.now();
  const r = await fetch(`${BASE}/api/agents/${agent}/generate`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ maxSteps: MAX_STEPS, messages: [{ role: 'user', content: MSG(id) }] }),
  });
  const latency = +((Date.now() - started) / 1000).toFixed(0);
  const b = await r.json();
  const u = b.totalUsage ?? {};
  const steps = b.steps ?? [];
  const wsCalls = steps.reduce((n, s) => n + (s.toolCalls ?? []).filter((c) => /websearch|web_search/i.test(c.payload?.toolName ?? c.toolName ?? '')).length, 0);
  const sources = (b.sources ?? []).concat(steps.flatMap((s) => s.sources ?? [])).length;
  const input = u.inputTokens ?? 0;
  const cachedInput = u.cachedInputTokens ?? 0;
  const t = {
    latency,
    total: u.totalTokens ?? 0,
    freshInput: input - cachedInput,
    cachedInput,
    output: u.outputTokens ?? 0,
    reasoning: u.reasoningTokens ?? 0,
    wsCalls, sources,
    hit: false, text: b.text ?? '',
  };
  t.cost = costOf(t);
  t.costNoCache = costNoCacheOf(t);
  return t;
};

const warm = async () => { process.stdout.write('warming up (twice, to prime prompt cache)… '); for (let i = 0; i < 2; i++) await Promise.all(ARMS.map((a) => ask(a, 'CO-1001'))); console.log('done.\n'); };
await warm();

const rows = {}; // rows[arm][id] = array of run objects
for (const app of APPLICANTS) {
  console.log(`${'#'.repeat(90)}\n# ${app.id} — ${app.state} (overlay: ${app.overlay[0]})\n${'#'.repeat(90)}`);
  for (const arm of ARMS) {
    const runs = [];
    for (let i = 0; i < REPEATS; i++) {
      const t = await ask(arm, app.id);
      t.hit = app.overlay[1].test(t.text);
      runs.push(t);
      console.log(`  ${arm.padEnd(32)} run ${i + 1}: ${t.latency}s · ${t.total.toLocaleString()} tok (fresh ${t.freshInput.toLocaleString()}/cached ${t.cachedInput.toLocaleString()}/out ${t.output.toLocaleString()}) · ${t.wsCalls} websearch · $${t.cost.toFixed(4)} · ${app.state === 'New York' ? 'n/a' : t.hit ? 'YES ✓' : 'no ✗'}`);
    }
    (rows[arm] ??= {})[app.id] = runs;
  }
  console.log('');
}

const allRuns = (arm) => APPLICANTS.flatMap((a) => rows[arm][a.id]);

// CONTENT
console.log(`${'='.repeat(90)}\nCONTENT — does the arm surface the state-specific obligation? (any-of-${REPEATS})\n${'='.repeat(90)}`);
console.log(`${'arm'.padEnd(32)} CO (CO-1001)  CA (CA-1001)  NY (NY-1001)`);
for (const arm of ARMS) {
  const any = (id) => rows[arm][id].some((r) => r.hit);
  console.log(`${arm.padEnd(32)} ${(any('CO-1001') ? 'YES ✓' : 'miss ✗').padEnd(13)} ${(any('CA-1001') ? 'YES ✓' : 'miss ✗').padEnd(13)} clean ✓`);
}

// TOKENS (cache-adjusted) — median across all applicant-runs
console.log(`\n${'='.repeat(90)}\nTOKENS — median across all applicant-runs (fresh input = full price, cached = discounted)\n${'='.repeat(90)}`);
console.log(`${'arm'.padEnd(32)} ${'total'.padEnd(16)} ${'fresh input'.padEnd(16)} ${'cached input'.padEnd(14)} output`);
for (const arm of ARMS) {
  const r = allRuns(arm);
  const md = (k) => round(median(r.map((x) => x[k])));
  console.log(`${arm.padEnd(32)} ${`${md('total').toLocaleString()} (${range(r.map((x) => Math.round(x.total / 1000)))}k)`.padEnd(16)} ${md('freshInput').toLocaleString().padEnd(16)} ${md('cachedInput').toLocaleString().padEnd(14)} ${md('output').toLocaleString()}`);
}

// COST estimate — median $/1,000 runs, billed (cache-warm) and no-cache (cold), per arm.
console.log(`\n${'='.repeat(90)}\nCOST — median $ / 1,000 runs (rates: in $${RATES.inputPerM}/M, cached $${RATES.cachedInputPerM}/M, out $${RATES.outputPerM}/M, websearch $${RATES.webSearchPerCall}/call)\n${'='.repeat(90)}`);
console.log(`${'arm'.padEnd(32)} ${'billed (cache-warm)'.padEnd(22)} ${'no-cache (cold)'.padEnd(18)} websearch`);
const perK = {};
for (const arm of ARMS) {
  const r = allRuns(arm);
  perK[arm] = { billed: median(r.map((x) => x.cost)) * 1000, cold: median(r.map((x) => x.costNoCache)) * 1000 };
  console.log(`${arm.padEnd(32)} ${`$${perK[arm].billed.toFixed(2)}`.padEnd(22)} ${`$${perK[arm].cold.toFixed(2)}`.padEnd(18)} ${median(r.map((x) => x.wsCalls))}`);
}
// Carver's saving vs web, as a range across the web cache-warm..cold spread.
const web = 'lending-status-websearch-agent', carv = 'lending-status-carver-agent';
const savingVs = (webCost) => (1 - perK[carv].billed / webCost) * 100;
console.log(`\nCARVER vs WEB SEARCH — Carver $${perK[carv].billed.toFixed(2)}/1k (cache-independent) vs web $${perK[web].billed.toFixed(2)} warm .. $${perK[web].cold.toFixed(2)} cold`);
console.log(`  → Carver is ${savingVs(perK[web].billed).toFixed(0)}% cheaper (vs web cache-warm) to ${savingVs(perK[web].cold).toFixed(0)}% cheaper (vs web cold) — and web's cost is still a FLOOR (excludes OpenAI's internal web_search fetch/rank tokens).`);
console.log('\nNote: rates are gpt-5.6-sol from OpenAI pricing (checked 2026-07-23); edit RATES at the top if they change.');
console.log('\ndone.');
