/**
 * State-lending counterfactual swap: hold one loan denial fixed, change ONLY the applicant's
 * state, and see whether each arm tracks the obligation that varies by state.
 *
 * Fixed request: a HOME-IMPROVEMENT loan (so California's Holden Act, which governs 1-4 unit
 * owner-occupied housing finance, is in scope) DECLINED by an AUTOMATED underwriting model (so
 * Colorado's AI Act ADMT duties are in scope). The state is injected in the system message; the
 * user turn is a naive "what happens next" and names no statute, agency, or obligation.
 *
 * The discriminating truth (researched, see docs):
 *   - Federal ECOA/Reg B + FCRA apply in every state (the common floor).
 *   - Colorado adds AI-Act (SB 24-205 / SB 26-189) ADMT duties on an automated adverse decision.
 *   - California adds the Holden Act Fair Lending Notice + specific-reasons duty for home loans.
 *   - New York adds no material overlay — the correct answer is the federal floor alone.
 * So an arm that is doing real work should emit DIFFERENT obligations for CO vs CA vs NY.
 *
 * Usage: node scripts/state-lending-probe.mjs [repeats]
 */
const BASE = process.env.MASTRA_URL ?? 'http://localhost:4111';
const MAX_STEPS = 8;

const caseFor = (state) => `Application 7788 — a home-improvement loan secured by the applicant's own
one-to-four-unit residence in ${state}. The file has been complete since submission.
Underwriting outcome: DECLINE. The decision was produced by the lender's automated underwriting
model (model score 611, below the 640 approval cutoff); the model weighed revolving utilisation,
employment tenure, and two aged collections accounts. Today's date is 15 January 2027.`;

const STATES = [
  { code: 'Colorado', overlay: ['CO AI-Act ADMT', /colorado ai act|SB ?24-?205|SB ?26-?189|automated decision|\bADMT\b|meaningful human review|human review of the (decision|denial)|artificial intelligence/i] },
  { code: 'California', overlay: ['CA Holden Act', /holden act|housing financial discrimination|fair lending notice/i] },
  { code: 'New York', overlay: ['(none — federal only)', /$^/] },
];

// Federal floor — should appear for every state.
const FEDERAL = [
  ['Reg B reasons/30-day', /30[- ]day|specific reason|principal reason|right to (a )?(statement|the )?reason|statement of (the )?reasons/i],
  ['FCRA credit-report', /credit report|consumer report|credit score|free (copy|report)|reporting agenc/i],
];

const ARMS = ['advisor-baseline-agent', 'advisor-websearch-agent', 'state-lending-carver-agent'];

const ask = async (agentKey, system, user) => {
  const started = Date.now();
  try {
    const res = await fetch(`${BASE}/api/agents/${agentKey}/generate`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ maxSteps: MAX_STEPS, messages: [{ role: 'system', content: system }, { role: 'user', content: user }] }),
    });
    const latency = ((Date.now() - started) / 1000).toFixed(0);
    if (!res.ok) return { latency, error: `${res.status}` };
    const b = await res.json();
    return { latency, text: b.text ?? '', toolCalls: (b.steps ?? []).reduce((n, s) => n + (s.toolCalls?.length ?? 0), 0) };
  } catch (e) { return { error: String(e) }; }
};

const USER = `Has there been a decision on my application yet — and if it's declined, what happens next and what will I receive?`;

const warm = async () => { process.stdout.write('warming up… '); await Promise.all(ARMS.map((a) => ask(a, 'You are a helpful assistant.', 'Reply: ready.'))); console.log('done.\n'); };

const REPEATS = Number(process.argv[2] ?? 1);
await warm();

const grid = {}; // arm -> state -> {overlayHit, fed}
for (const st of STATES) {
  console.log(`\n${'#'.repeat(84)}\n# STATE = ${st.code}   (overlay that should appear: ${st.overlay[0]})\n${'#'.repeat(84)}`);
  const system = `You are the customer-facing assistant on the lender's website. The person you are speaking with is the signed-in applicant themselves.\n\n${caseFor(st.code)}`;
  for (const arm of ARMS) {
    let best = null;
    for (let i = 0; i < REPEATS; i++) {
      const r = await ask(arm, system, USER);
      if (!r.error) { r.overlayHit = st.overlay[1].test(r.text); r.fed = FEDERAL.filter(([, re]) => re.test(r.text)).length; best = r; }
      else best = r;
    }
    (grid[arm] ??= {})[st.code] = best;
    if (best.error) { console.log(`  ${arm.padEnd(28)} ERROR ${best.error}`); continue; }
    console.log(`  ${arm.padEnd(28)} ${best.latency}s tools=${best.toolCalls}  federal ${best.fed}/2  ·  ${st.overlay[0]}: ${st.code === 'New York' ? '(n/a)' : best.overlayHit ? 'YES ✓' : 'no ✗'}`);
  }
}

// Counterfactual sensitivity: did each arm actually change its state-specific content?
console.log(`\n\n${'='.repeat(84)}\nSUMMARY — does the arm track the state-specific overlay?\n${'='.repeat(84)}`);
console.log(`${'arm'.padEnd(28)} CO AI-Act    CA Holden     NY (should be federal-only)`);
for (const arm of ARMS) {
  const co = grid[arm]['Colorado'], ca = grid[arm]['California'], ny = grid[arm]['New York'];
  const mark = (r, expect) => r?.error ? 'ERR' : r.overlayHit === expect ? (expect ? 'YES ✓' : 'clean ✓') : (expect ? 'MISS ✗' : 'invented ✗');
  // NY: "clean" if it did NOT assert a CO/CA-style overlay; we check it didn't falsely cite Holden/CO-AI
  const nyClean = ny && !ny.error && !/holden|colorado ai|SB ?24-?205|SB ?26-?189/i.test(ny.text);
  console.log(`${arm.padEnd(28)} ${mark(co, true).padEnd(12)} ${mark(ca, true).padEnd(13)} ${nyClean ? 'clean ✓' : 'leaked ✗'}`);
}
console.log('\ndone.');
