/**
 * Lending-status demo scorecard + operational-cost harness.
 *
 * The applicant NEVER states their state. They ask for their loan status and give an applicant ID;
 * the agent calls lookupApplicant (an auth/CRM stand-in) which returns their file — including the
 * state — and then answers. Three applicant IDs, one per state, identical loan and denial: the
 * state is the only variable. A grounded arm that is doing real work surfaces the obligation that
 * varies by that state (Colorado AI Act, California Holden Act); New York has none.
 *
 * Two things are measured, per (arm × applicant), over `repeats` runs:
 *   - CONTENT: does the arm surface the state obligation? (the demo's correctness claim)
 *   - OPERATIONAL COST: latency, tool-calls, and token burn (in/out/reasoning/total), plus their
 *     spread across repeats (reproducibility). This is the Carver-vs-web operational story.
 *
 * Usage: node scripts/lending-status-probe.mjs [repeats]   (default 1; use 3 for the cost table)
 */
const BASE = process.env.MASTRA_URL ?? 'http://localhost:4111';
const MAX_STEPS = 8;
const REPEATS = Number(process.argv[2] ?? 1);

const APPLICANTS = [
  { id: 'CO-1001', state: 'Colorado', overlay: ['CO AI-Act', /colorado ai act|SB ?24-?205|SB ?26-?189|meaningful human review|automated decision.{0,45}(disclos|notice|explan|review)/i] },
  { id: 'CA-1001', state: 'California', overlay: ['CA Holden Act', /holden act|housing financial discrimination|fair lending notice/i] },
  { id: 'NY-1001', state: 'New York', overlay: ['(none — federal only)', /$^/] },
];
const ARMS = ['lending-status-baseline-agent', 'lending-status-websearch-agent', 'lending-status-carver-agent'];
const MSG = (id) => `Hi, can you check the status of my loan application? My applicant ID is ${id}.`;

const toolNames = (b) => (b.steps ?? []).flatMap((s) => (s.toolCalls ?? []).map((c) => c.payload?.toolName ?? c.toolName)).filter(Boolean);
const median = (xs) => { if (!xs.length) return 0; const s = [...xs].sort((a, b) => a - b); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : Math.round((s[m - 1] + s[m]) / 2); };
const range = (xs) => (xs.length ? `${Math.min(...xs)}–${Math.max(...xs)}` : '—');

const ask = async (agent, id) => {
  const started = Date.now();
  const r = await fetch(`${BASE}/api/agents/${agent}/generate`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ maxSteps: MAX_STEPS, messages: [{ role: 'user', content: MSG(id) }] }),
  });
  const latency = +((Date.now() - started) / 1000).toFixed(0);
  const b = await r.json();
  const u = b.totalUsage ?? {};
  return {
    latency, tools: toolNames(b), text: b.text ?? '',
    toolCalls: (b.steps ?? []).reduce((n, s) => n + (s.toolCalls?.length ?? 0), 0),
    tokensIn: u.inputTokens ?? 0, tokensOut: u.outputTokens ?? 0,
    tokensReasoning: u.reasoningTokens ?? 0, tokensTotal: u.totalTokens ?? 0,
  };
};

const warm = async () => { process.stdout.write('warming up… '); await Promise.all(ARMS.map((a) => ask(a, 'CO-1001'))); console.log('done.\n'); };
await warm();

// rows[arm][id] = { hits:[bool], latencies:[], toolCalls:[], tokens:[] }
const rows = {};
for (const app of APPLICANTS) {
  console.log(`${'#'.repeat(84)}\n# ${app.id} — ${app.state} (overlay: ${app.overlay[0]})\n${'#'.repeat(84)}`);
  for (const arm of ARMS) {
    const cell = { hits: [], latencies: [], toolCalls: [], tokens: [], lookedUp: [] };
    for (let i = 0; i < REPEATS; i++) {
      const r = await ask(arm, app.id);
      cell.hits.push(app.overlay[1].test(r.text));
      cell.latencies.push(r.latency);
      cell.toolCalls.push(r.toolCalls);
      cell.tokens.push(r.tokensTotal);
      cell.lookedUp.push(r.tools.some((t) => /lookup/i.test(t)));
      console.log(`  ${arm.padEnd(32)} run ${i + 1}: ${r.latency}s · ${r.toolCalls} calls · ${r.tokensTotal.toLocaleString()} tok (in ${r.tokensIn.toLocaleString()}/out ${r.tokensOut.toLocaleString()}/reas ${r.tokensReasoning.toLocaleString()}) · ${app.overlay[0]}: ${app.state === 'New York' ? 'n/a' : app.overlay[1].test(r.text) ? 'YES ✓' : 'no ✗'}`);
    }
    (rows[arm] ??= {})[app.id] = cell;
  }
  console.log('');
}

// CONTENT scorecard
console.log(`${'='.repeat(84)}\nCONTENT — does the arm surface the state-specific obligation? (any-of-${REPEATS})\n${'='.repeat(84)}`);
console.log(`${'arm'.padEnd(32)} CO (CO-1001)  CA (CA-1001)  NY (NY-1001)`);
for (const arm of ARMS) {
  const any = (id) => rows[arm][id].hits.some(Boolean);
  console.log(`${arm.padEnd(32)} ${(any('CO-1001') ? 'YES ✓' : 'miss ✗').padEnd(13)} ${(any('CA-1001') ? 'YES ✓' : 'miss ✗').padEnd(13)} clean ✓`);
}

// OPERATIONAL cost — Carver vs web is the story. Median across all applicant-runs per arm.
console.log(`\n${'='.repeat(84)}\nOPERATIONAL COST — median across all applicant-runs (range in parens)\n${'='.repeat(84)}`);
console.log(`${'arm'.padEnd(32)} ${'latency s'.padEnd(16)} ${'tool-calls'.padEnd(12)} ${'total tokens'}`);
for (const arm of ARMS) {
  const all = (k) => APPLICANTS.flatMap((a) => rows[arm][a.id][k]);
  const lat = all('latencies'), tc = all('toolCalls'), tok = all('tokens');
  console.log(`${arm.padEnd(32)} ${`${median(lat)} (${range(lat)})`.padEnd(16)} ${`${median(tc)} (${range(tc)})`.padEnd(12)} ${median(tok).toLocaleString()} (${range(tok.map((t) => Math.round(t / 1000)))}k)`);
}
console.log('\ndone.');
