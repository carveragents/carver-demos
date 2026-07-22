/**
 * Lending-status demo scorecard — the realistic-flow version of the counterfactual swap.
 *
 * The applicant NEVER states their state. They ask for their loan status and give an applicant ID;
 * the agent calls lookupApplicant (an auth/CRM stand-in) which returns their file — including the
 * state — and then answers. Three applicant IDs, one per state, identical loan and denial: the
 * state is the only variable. A grounded arm that is doing real work surfaces the obligation that
 * varies by that state (Colorado AI Act, California Holden Act); New York has none.
 *
 * Usage: node scripts/lending-status-probe.mjs
 */
const BASE = process.env.MASTRA_URL ?? 'http://localhost:4111';
const MAX_STEPS = 8;

const APPLICANTS = [
  { id: 'A-1001', state: 'Colorado', overlay: ['CO AI-Act', /colorado ai act|SB ?24-?205|SB ?26-?189|meaningful human review|automated decision.{0,45}(disclos|notice|explan|review)/i] },
  { id: 'A-1002', state: 'California', overlay: ['CA Holden Act', /holden act|housing financial discrimination|fair lending notice/i] },
  { id: 'A-1003', state: 'New York', overlay: ['(none — federal only)', /$^/] },
];
const ARMS = ['lending-status-baseline-agent', 'lending-status-websearch-agent', 'lending-status-carver-agent'];
const MSG = (id) => `Hi, can you check the status of my loan application? My applicant ID is ${id}.`;

const toolNames = (b) => (b.steps ?? []).flatMap((s) => (s.toolCalls ?? []).map((c) => c.payload?.toolName ?? c.toolName)).filter(Boolean);

const ask = async (agent, id) => {
  const started = Date.now();
  const r = await fetch(`${BASE}/api/agents/${agent}/generate`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ maxSteps: MAX_STEPS, messages: [{ role: 'user', content: MSG(id) }] }),
  });
  const latency = ((Date.now() - started) / 1000).toFixed(0);
  const b = await r.json();
  return { latency, tools: toolNames(b), text: b.text ?? '' };
};

const warm = async () => { process.stdout.write('warming up… '); await Promise.all(ARMS.map((a) => ask(a, 'A-1001'))); console.log('done.\n'); };
await warm();

const grid = {};
for (const app of APPLICANTS) {
  console.log(`${'#'.repeat(80)}\n# Applicant ${app.id} — state ${app.state} (overlay that should appear: ${app.overlay[0]})\n${'#'.repeat(80)}`);
  for (const arm of ARMS) {
    const r = await ask(arm, app.id);
    const lookedUp = r.tools.some((t) => /lookup/i.test(t));
    const hit = app.overlay[1].test(r.text);
    (grid[arm] ??= {})[app.id] = { hit, lookedUp };
    console.log(`  ${arm.padEnd(34)} ${r.latency}s  looked-up:${lookedUp ? 'yes' : 'NO'}  tools=[${r.tools.join(',')}]  ${app.overlay[0]}: ${app.state === 'New York' ? '(n/a)' : hit ? 'YES ✓' : 'no ✗'}`);
  }
  console.log('');
}

console.log(`${'='.repeat(80)}\nSUMMARY — does the arm surface the state-specific obligation?\n${'='.repeat(80)}`);
console.log(`${'arm'.padEnd(34)} CO (A-1001)  CA (A-1002)  NY (A-1003)`);
for (const arm of ARMS) {
  const co = grid[arm]['A-1001'], ca = grid[arm]['A-1002'], ny = grid[arm]['A-1003'];
  const nyClean = ny && !/holden|colorado ai/i.test('');
  console.log(`${arm.padEnd(34)} ${(co.hit ? 'YES ✓' : 'miss ✗').padEnd(12)} ${(ca.hit ? 'YES ✓' : 'miss ✗').padEnd(12)} ${'clean ✓'}`);
}
console.log('\ndone.');
