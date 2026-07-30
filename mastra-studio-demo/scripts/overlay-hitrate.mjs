/**
 * Per-arm, per-applicant HIT RATE for the state overlay. Generalised from web-co-hitrate.mjs.
 *
 * WHY THIS EXISTS: lending-status-probe.mjs scores any-of-N — a `YES` only proves the arm surfaced
 * the obligation at least ONCE in N runs. That is enough to show an arm CAN, but not enough to
 * narrate "every time" (Carver) or "never" (web). The demo video makes reliability claims about
 * both, so both need a rate. See docs/LESSONS.md on per-case reporting.
 *
 * Same message, same maxSteps, and the VERBATIM overlay regexes from lending-status-probe.mjs, so
 * results are directly comparable to the scorecard.
 *
 * Usage: node scripts/overlay-hitrate.mjs <arm> <applicant> [runs]
 *   arm:       baseline | websearch | carver
 *   applicant: CO-1001 | CA-1001
 * e.g. node scripts/overlay-hitrate.mjs carver CO-1001 8
 */
const BASE = process.env.MASTRA_URL ?? 'http://localhost:4111';

const ARMS = {
  baseline: 'lending-status-baseline-agent',
  websearch: 'lending-status-websearch-agent',
  carver: 'lending-status-carver-agent',
};

// CO/CA verbatim from lending-status-probe.mjs.
//
// NY is the CONTROL and is scored INVERSELY: New York has no equivalent state duty, so a match is a
// FALSE POSITIVE — the arm asserting another state's obligation for a New York applicant. Zero
// matches means the arm is correctly silent, which is what makes "the answer changes exactly where
// the law changes, and only there" a finding rather than verbosity.
const OVERLAYS = {
  'CO-1001': ['CO AI-Act', /colorado ai act|SB ?24-?205|SB ?26-?189|meaningful human review|automated decision.{0,45}(disclos|notice|explan|review)/i],
  'CA-1001': ['CA Holden Act', /holden act|housing financial discrimination|fair lending notice/i],
  'NY-1001': ['a state overlay it should NOT claim', /colorado ai act|SB ?24-?205|SB ?26-?189|holden act|housing financial discrimination|fair lending notice/i],
};
const INVERTED = new Set(['NY-1001']);

const [armKey, applicantId, runsArg] = process.argv.slice(2);
const agent = ARMS[armKey];
const overlay = OVERLAYS[applicantId];
const RUNS = Number(runsArg ?? 8);

if (!agent || !overlay) {
  console.error('Usage: node scripts/overlay-hitrate.mjs <baseline|websearch|carver> <CO-1001|CA-1001|NY-1001> [runs]');
  process.exit(1);
}

const [overlayName, overlayRe] = overlay;
const MSG = `Hi, can you check the status of my loan application? My applicant ID is ${applicantId}.`;

const ask = async () => {
  const r = await fetch(`${BASE}/api/agents/${agent}/generate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ maxSteps: 8, messages: [{ role: 'user', content: MSG }] }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()).text ?? '';
};

console.log(`${agent} × ${applicantId} — looking for ${overlayName}, ${RUNS} runs\n`);

let hits = 0;
for (let i = 1; i <= RUNS; i++) {
  let text;
  try {
    text = await ask();
  } catch (e) {
    console.log(`run ${i}: ERROR ${e.message} (not counted)`);
    continue;
  }
  const m = text.match(overlayRe);
  if (m) hits++;
  const inv = INVERTED.has(applicantId);
  console.log(`run ${i}: ${m ? `${inv ? 'FALSE POSITIVE' : 'HIT'}  — "${m[0]}"` : (inv ? 'correctly silent' : 'miss')}`);
}

const pct = Math.round((hits / RUNS) * 100);
if (INVERTED.has(applicantId)) {
  console.log(`\n${armKey} on ${applicantId} (CONTROL): ${RUNS - hits}/${RUNS} correctly silent; ${hits} false positive(s)`);
} else {
  console.log(`\n${armKey} on ${applicantId}: ${hits}/${RUNS} (${pct}%) surfaced ${overlayName}`);
}
