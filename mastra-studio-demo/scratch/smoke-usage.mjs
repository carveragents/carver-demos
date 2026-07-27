/**
 * Phase 0 smoke test: does the response carry a CACHED-INPUT token split?
 * The whitepaper's §3 web-arm number cites 9,678 cached tokens, so a split existed somewhere;
 * this confirms which field carries it on the current SDK, or proves it is unavailable
 * (in which case all input is priced fresh and the cost is labelled an upper bound).
 */
const BASE = process.env.MASTRA_URL ?? 'http://localhost:4112';
const MAX_STEPS = 8;

const ask = async (agentKey, system, user) => {
  const started = Date.now();
  const res = await fetch(`${BASE}/api/agents/${agentKey}/generate`, {
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
  const latency = Date.now() - started;
  if (!res.ok) return { error: `${res.status} ${(await res.text()).slice(0, 300)}`, latency };
  return { body: await res.json(), latency };
};

const SYSTEM =
  'You are the assistant for the operations team at a fintech company. About the company: it offers custody and exchange services for crypto-assets, including stablecoins, to retail and professional clients, and is headquartered and operating in Italy. It has run this service since 2021 and holds no crypto-specific licence or authorisation; it currently relies on a local registration. The person you are speaking with is a member of the operations team. Today\'s date is 15 June 2026.';
const USER =
  "We're locking down the roadmap for the second half of the year. Is there anything we need to sort out on the regulatory side, or are we fine to keep operating the service as we are?";

const arm = process.argv[2] ?? 'crypto-carver-agent';
const passes = Number(process.argv[3] ?? 2);

for (let i = 1; i <= passes; i++) {
  const { body, latency, error } = await ask(arm, SYSTEM, USER);
  if (error) {
    console.log(`pass ${i}: ERROR ${error}`);
    continue;
  }
  console.log(`\n===== ${arm} pass ${i} — ${latency} ms =====`);
  console.log('top-level keys:', Object.keys(body).join(', '));
  console.log('totalUsage:', JSON.stringify(body.totalUsage));
  const steps = body.steps ?? [];
  console.log(`steps: ${steps.length}`);
  steps.forEach((st, n) => {
    console.log(`  step ${n}: keys=${Object.keys(st).join(',')} toolCalls=${st.toolCalls?.length ?? 0}`);
    if (st.usage) console.log(`    usage: ${JSON.stringify(st.usage)}`);
    if (st.providerMetadata) console.log(`    providerMetadata: ${JSON.stringify(st.providerMetadata).slice(0, 500)}`);
  });
  if (body.providerMetadata) console.log('providerMetadata:', JSON.stringify(body.providerMetadata).slice(0, 800));
  if (body.response?.body) console.log('response.body keys:', Object.keys(body.response.body).join(','));
  console.log('answer (first 300):', String(body.text ?? '').slice(0, 300).replace(/\n/g, ' '));
}
