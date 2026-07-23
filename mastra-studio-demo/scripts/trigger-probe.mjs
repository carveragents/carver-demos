/**
 * Silent-trigger probe, cross-domain edition — OPERATIONAL-COST harness.
 *
 * The content question ("does the arm notice an obligation nobody named?") was measured first
 * and answered: on publicly-retrievable obligations the web-search arm reaches parity with the
 * Carver arm, so answer content does not separate them (see docs/DEMO.md). What separates them
 * is operational, and this harness measures it across the three arm types:
 *
 *   - latency          wall-clock seconds per answer
 *   - tool calls        how many retrieval round-trips the arm made
 *   - token burn        input / output / reasoning / total tokens (totalUsage)
 *   - reproducibility   spread of the above across REPEATS identical runs
 *
 * Content is still scored (the mechanical CHECKS) as a guard: an arm that got faster/cheaper by
 * getting the answer wrong should be visible, not rewarded.
 *
 * Every arm runs under the SAME step cap (MAX_STEPS) so the comparison is fair — it disciplines
 * the Carver arm's documented thrashing without touching the web arm (whose provider-defined
 * webSearch does its many sub-searches inside a single tool call).
 *
 * The actor context is a SYSTEM message (a signed-in operator's situation); the user turn is a
 * naive planning question naming no rule, deadline, or regulator. See the design notes in git.
 *
 * Usage: node scripts/trigger-probe.mjs [crypto|device|child-safety|all] [repeats]
 */
const BASE = process.env.MASTRA_URL ?? 'http://localhost:4111';
const MAX_STEPS = 8;
const DEFAULT_REPEATS = 3;

const SCENARIOS = [
  {
    id: 'crypto',
    label: 'Crypto CASP authorisation (EU / MiCA transition)',
    carver: 'crypto-carver-agent',
    system: `You are the assistant for the operations team at a fintech company. About the company: it offers custody and exchange services for crypto-assets, including stablecoins, to retail and professional clients, and is headquartered and operating in Italy. It has run this service since 2021 and holds no crypto-specific licence or authorisation; it currently relies on a local registration. The person you are speaking with is a member of the operations team. Today's date is 15 June 2026.`,
    user: `We're locking down the roadmap for the second half of the year. Is there anything we need to sort out on the regulatory side, or are we fine to keep operating the service as we are?`,
    checks: [
      ['names authorisation/CASP', /\bCASP\b|authoris|licen[sc]e|registration under mica/i],
      ['names MiCA', /\bMiCA\b|markets in crypto/i],
      ['the 2026 deadline', /1 july 2026|by 1 july|before 1 july|transition (period )?(will )?(end|expir|clos)|30 (december|dec) 2024|mid-?2026/i],
      ['must cease if unlicensed', /cease|stop (offering|onboarding|operating|providing)|may not (continue|operate|offer)|cannot (continue|operate|offer)|wind down/i],
      ['cites a link', /https?:\/\//i],
    ],
  },
  {
    id: 'device',
    label: 'Medical-device swissdamed registration (Switzerland)',
    carver: 'device-carver-agent',
    system: `You are the assistant for the regulatory-affairs team at a medical-device manufacturer. About the company: it makes in-vitro diagnostic (IVD) devices and sells them across Europe, including Switzerland, through a local authorised representative. The person you are speaking with is on the regulatory-affairs team. Today's date is 20 June 2026.`,
    user: `We're refreshing our market-access checklist for the next quarter. Is there anything we need to take care of to keep selling into our current European markets?`,
    checks: [
      ['names Switzerland/Swissmedic', /switzerland|swiss|swissmedic/i],
      ['names registration/swissdamed', /swissdamed|registration|register|\bUDI\b/i],
      ['the 2026 deadline', /1 july 2026|july 2026|by 1 july|from 1 july/i],
      ['mandatory before placing', /before (placing|first market|selling)|mandatory|required to (sell|place|register)|cannot (sell|place)|prerequisite/i],
      ['cites a link', /https?:\/\//i],
    ],
  },
  {
    id: 'child-safety',
    label: 'Online child-safety age assurance (UK / Italy / California)',
    carver: 'child-safety-carver-agent',
    system: `You are the assistant for the product team at a company that runs a social chat app with AI companions. About the product: it has a general-audience user base that includes teenagers under 16, and it is available in the United Kingdom, Italy, and California. The person you are speaking with is a product manager. Today's date is 1 July 2026.`,
    user: `We're finalising the next release and locking scope. Is there anything we need to build in before we ship it to our markets?`,
    checks: [
      ['names age assurance/verification', /age (assurance|verification|check|gating)|verify.{0,10}age|minimum age/i],
      ['scoped to minors/under-16', /minor|under.?16|under 16|children|teen|young (people|user)/i],
      ['a specific jurisdiction rule', /\bICO\b|garante|\bCNIL\b|california|italy|united kingdom|children'?s code|age-appropriate|SB \d/i],
      ['parental/verifiable consent', /parental consent|verifiable (parental )?consent|guardian consent|parental control/i],
      ['cites a link', /https?:\/\//i],
    ],
  },
];

const ARM_TYPES = [
  ['baseline', () => 'advisor-baseline-agent'],
  ['web search', () => 'advisor-websearch-agent'],
  ['carver', (s) => s.carver],
];

const median = (xs) => {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const range = (xs) => (xs.length ? `${Math.min(...xs)}–${Math.max(...xs)}` : '—');

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
    return { error: String(err), latency: (Date.now() - started) / 1000 };
  }
  const latency = (Date.now() - started) / 1000;
  if (!res.ok) return { error: `${res.status} ${(await res.text()).slice(0, 200)}`, latency };
  const b = await res.json();
  const steps = b.steps ?? [];
  const toolCalls = steps.reduce((n, st) => n + (st.toolCalls?.length ?? 0), 0);
  const u = b.totalUsage ?? {};
  return {
    latency,
    stepCount: steps.length,
    toolCalls,
    tokensIn: u.inputTokens ?? 0,
    tokensOut: u.outputTokens ?? 0,
    tokensReasoning: u.reasoningTokens ?? 0,
    tokensTotal: u.totalTokens ?? 0,
    text: b.text ?? '',
  };
};

const score = (checks, text = '') => checks.filter(([, re]) => re.test(text)).map(([n]) => n).length;

const warmup = async () => {
  const agents = [...new Set(SCENARIOS.flatMap((s) => ARM_TYPES.map(([, pick]) => pick(s))))];
  process.stdout.write(`warming up ${agents.length} agents (maxSteps=${MAX_STEPS})… `);
  await Promise.all(agents.map((a) => ask(a, { system: 'You are a helpful assistant.', user: 'Reply with the single word: ready.' })));
  console.log('done.\n');
};

const rows = []; // { scenario, arm, latencies, tokens, toolCalls, scores }

const run = async (scenario, repeats) => {
  console.log(`\n${'#'.repeat(80)}\n# ${scenario.label}\n${'#'.repeat(80)}`);
  for (const [armName, pick] of ARM_TYPES) {
    const agentKey = pick(scenario);
    const runs = [];
    for (let i = 0; i < repeats; i++) {
      const r = await ask(agentKey, scenario);
      if (r.error) {
        console.log(`  ${armName.padEnd(11)} run ${i + 1}: ERROR ${r.error}`);
        continue;
      }
      r.scoreHits = score(scenario.checks, r.text);
      runs.push(r);
      console.log(
        `  ${armName.padEnd(11)} run ${i + 1}: ${r.latency.toFixed(1)}s · ${r.toolCalls} tool-calls · ` +
          `${r.tokensTotal.toLocaleString()} tok (in ${r.tokensIn.toLocaleString()}/out ${r.tokensOut.toLocaleString()}/reas ${r.tokensReasoning.toLocaleString()}) · content ${r.scoreHits}/${scenario.checks.length}`,
      );
    }
    if (runs.length) {
      rows.push({
        scenario: scenario.id,
        arm: armName,
        latencies: runs.map((r) => +r.latency.toFixed(1)),
        tokens: runs.map((r) => r.tokensTotal),
        toolCalls: runs.map((r) => r.toolCalls),
        scores: runs.map((r) => r.scoreHits),
        checkN: scenario.checks.length,
      });
    }
  }
};

const summary = () => {
  console.log(`\n\n${'='.repeat(96)}\nOPERATIONAL SUMMARY  (median of ${REPEATS} runs; range in parens)\n${'='.repeat(96)}`);
  console.log(`${'scenario'.padEnd(13)} ${'arm'.padEnd(11)} ${'latency s'.padEnd(16)} ${'tool-calls'.padEnd(12)} ${'tokens'.padEnd(22)} content`);
  for (const r of rows) {
    const lat = `${median(r.latencies)} (${range(r.latencies)})`;
    const tc = `${median(r.toolCalls)} (${range(r.toolCalls)})`;
    const tok = `${median(r.tokens).toLocaleString()} (${range(r.tokens.map((t) => Math.round(t / 1000)))}k)`;
    const sc = `${median(r.scores)}/${r.checkN} (${range(r.scores)})`;
    console.log(`${r.scenario.padEnd(13)} ${r.arm.padEnd(11)} ${lat.padEnd(16)} ${tc.padEnd(12)} ${tok.padEnd(22)} ${sc}`);
  }
  // Aggregate by arm type across scenarios — the headline operational-cost comparison.
  console.log(`\n${'-'.repeat(96)}\nBY ARM TYPE (median across all scenario-runs)\n${'-'.repeat(96)}`);
  console.log(`${'arm'.padEnd(11)} ${'latency s'.padEnd(12)} ${'tool-calls'.padEnd(12)} ${'total tokens'.padEnd(14)} ${'content'}`);
  for (const [armName] of ARM_TYPES) {
    const mine = rows.filter((r) => r.arm === armName);
    const lat = median(mine.flatMap((r) => r.latencies));
    const tc = median(mine.flatMap((r) => r.toolCalls));
    const tok = median(mine.flatMap((r) => r.tokens));
    const sc = median(mine.flatMap((r) => r.scores.map((v) => v / r.checkN)));
    console.log(`${armName.padEnd(11)} ${String(lat).padEnd(12)} ${String(tc).padEnd(12)} ${String(tok?.toLocaleString()).padEnd(14)} ${(sc * 100).toFixed(0)}%`);
  }
};

const which = process.argv[2] ?? 'all';
const REPEATS = Number(process.argv[3] ?? DEFAULT_REPEATS);
const chosen = which === 'all' ? SCENARIOS : SCENARIOS.filter((s) => s.id === which);
if (chosen.length === 0) {
  console.error(`Unknown scenario "${which}". Known: ${SCENARIOS.map((s) => s.id).join(', ')}, all`);
  process.exit(1);
}
await warmup();
for (const s of chosen) await run(s, REPEATS);
summary();
