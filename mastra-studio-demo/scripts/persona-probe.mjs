/**
 * Persona-obligation probe: does an agent notice an obligation nobody named?
 *
 * The persona is injected as a system message (a signed-in user's attributes), never typed
 * into the question. That is the whole point — if the persona sits in the user turn it acts
 * as a search string and the web-search arm can retrieve on it directly.
 *
 * Runs the same scenario under two deployment framings so we can pick the stronger one.
 *
 * Usage: node persona-probe.mjs [consumer|institution|both]
 */
const BASE = process.env.MASTRA_URL ?? 'http://localhost:4111';
const ARMS = ['lending-baseline-agent', 'lending-websearch-agent', 'lending-carver-agent'];

// Shared case facts. Two planted obligations, neither named in the user turn:
//   1. Adverse action notice must give SPECIFIC principal reasons (Reg B § 1002.9).
//   2. Application was submitted 34 days ago; the notification window is 30 days.
const CASE = `Application 4471 — $12,000 unsecured personal loan.
Applicant: Marcus Webb, age 39, Colorado. Employed 7 months at current employer.
Submitted 34 days ago; the file has been complete since submission.
Underwriting outcome: DECLINE. Automated model score 611, below the 640 cutoff.
Contributing factors recorded by the model: revolving utilisation 88%, short tenure at
current employer, two collections accounts aged 3 years.`;

const FRAMINGS = {
  consumer: {
    system: `You are the customer-facing assistant on the lender's website. The person you are
speaking with is the signed-in applicant themselves.

${CASE}`,
    user: `Hi — has there been any decision on my application yet?`,
  },
  institution: {
    system: `You are an internal assistant for the lender's credit operations team. The person
you are speaking with is a loan officer at the company.

${CASE}`,
    user: `4471 came back a decline. Put together what we send the applicant.`,
  },
};

const ask = async (agentKey, { system, user }) => {
  const started = Date.now();
  const res = await fetch(`${BASE}/api/agents/${agentKey}/generate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user },
      ],
    }),
  });
  const elapsed = ((Date.now() - started) / 1000).toFixed(1);
  if (!res.ok) return { agentKey, elapsed, error: `${res.status} ${await res.text()}` };

  const body = await res.json();
  const text = body.text ?? body.response?.text ?? JSON.stringify(body).slice(0, 400);
  const toolCalls = [...JSON.stringify(body).matchAll(/"toolName":"([^"]+)"/g)].map((m) => m[1]);
  const tools = toolCalls.reduce((acc, t) => ({ ...acc, [t]: (acc[t] ?? 0) + 1 }), {});
  return { agentKey, elapsed, text, tools };
};

// Scored mechanically so the verdict does not rest on my reading of the transcripts.
const CHECKS = [
  ['specific reasons', /611|640|88%|utilis|utiliz|tenure|collections/i],
  ['30-day timing', /30[- ]day|30 days|thirty days|34 days|late|overdue|past due/i],
  ['names ECOA/Reg B', /regulation b|reg\.? b\b|ecoa|equal credit opportunity|1002\.9/i],
  ['right to reasons', /right to (a )?(statement|specific)|request the (specific )?reasons|statement of reasons/i],
  ['cites a link', /https?:\/\//i],
];

const score = (text = '') => CHECKS.filter(([, re]) => re.test(text)).map(([name]) => name);

const run = async (framingName) => {
  const framing = FRAMINGS[framingName];
  console.log(`\n\n${'#'.repeat(78)}\n# FRAMING: ${framingName}\n# USER: ${framing.user}\n${'#'.repeat(78)}`);
  for (const arm of ARMS) {
    const r = await ask(arm, framing);
    const hits = r.text ? score(r.text) : [];
    console.log(`\n${'='.repeat(78)}\n${r.agentKey}  —  ${r.elapsed}s`);
    if (r.tools && Object.keys(r.tools).length) {
      console.log(`tools: ${Object.entries(r.tools).map(([k, v]) => `${k}x${v}`).join(', ')}`);
    }
    console.log(`SCORE ${hits.length}/${CHECKS.length}: ${hits.join(', ') || '(none)'}`);
    console.log('='.repeat(78));
    console.log(r.error ? `ERROR: ${r.error}` : r.text);
  }
};

const which = process.argv[2] ?? 'both';
for (const f of which === 'both' ? Object.keys(FRAMINGS) : [which]) await run(f);
