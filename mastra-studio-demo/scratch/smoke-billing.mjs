/**
 * Phase 0 follow-up: the OpenAI response body exposes `billing` and `tool_usage`.
 * If billing carries a real charged amount, it beats reconstructing cost from a rates table —
 * and tool_usage would give the web arm's search-call count directly instead of by inference.
 */
const BASE = process.env.MASTRA_URL ?? 'http://localhost:4112';

const ask = async (agentKey, system, user) => {
  const res = await fetch(`${BASE}/api/agents/${agentKey}/generate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      maxSteps: 8,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user },
      ],
    }),
  });
  if (!res.ok) return { error: `${res.status} ${(await res.text()).slice(0, 300)}` };
  return { body: await res.json() };
};

const SYSTEM =
  'You are the assistant for the regulatory-affairs team at a medical-device manufacturer. About the company: it makes in-vitro diagnostic (IVD) devices and sells them across Europe, including Switzerland, through a local authorised representative. The person you are speaking with is on the regulatory-affairs team. Today\'s date is 20 June 2026.';
const USER =
  "We're refreshing our market-access checklist for the next quarter. Is there anything we need to take care of to keep selling into our current European markets?";

const arm = process.argv[2] ?? 'advisor-websearch-agent';
const { body, error } = await ask(arm, SYSTEM, USER);
if (error) {
  console.log('ERROR', error);
  process.exit(1);
}

console.log(`===== ${arm} =====`);
console.log('totalUsage:', JSON.stringify(body.totalUsage));
const steps = body.steps ?? [];
console.log(`\nsteps: ${steps.length}`);
steps.forEach((st, n) => {
  const tc = (st.toolCalls ?? []).map((c) => c.toolName ?? c.type ?? '?');
  console.log(`  step ${n}: tools=[${tc.join(',')}]  usage=${JSON.stringify(st.usage?.raw?.inputTokens ?? st.usage)}`);
  const rb = st.response?.body;
  if (rb?.billing) console.log(`    billing: ${JSON.stringify(rb.billing)}`);
  if (rb?.tool_usage) console.log(`    tool_usage: ${JSON.stringify(rb.tool_usage)}`);
  if (rb?.usage) console.log(`    body.usage: ${JSON.stringify(rb.usage)}`);
  if (rb?.model) console.log(`    model: ${rb.model} · service_tier=${rb.service_tier} · cache_retention=${rb.prompt_cache_retention}`);
});
console.log('\nsources:', JSON.stringify((body.sources ?? []).slice(0, 3)).slice(0, 400));
console.log('\nfinal body.billing:', JSON.stringify(body.response?.body?.billing));
console.log('final body.tool_usage:', JSON.stringify(body.response?.body?.tool_usage));
console.log('\nanswer (first 300):', String(body.text ?? '').slice(0, 300).replace(/\n/g, ' '));
