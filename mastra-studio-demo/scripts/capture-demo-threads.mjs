/**
 * Capture the nine demo conversations as re-openable Studio threads, for the demo video.
 *
 * WHY: the agents take 18-40s per answer. Generating live during a screen recording would put
 * 8-30s of dead air into every beat. Instead we run each conversation ONCE here, with an explicit
 * memory thread id, and the recorder later navigates to /agents/<arm>/chat/<threadId>. Everything
 * on screen is real captured output — same message, same agents, same index — just not generated
 * while the camera rolls. Requires memory (see src/mastra/memory.ts).
 *
 * The applicant NEVER names their state or any rule. They give an applicant ID; lookupApplicant
 * supplies the state. Do not change MSG — that invariant is the demo (docs/CONTINUING.md Hazards).
 *
 * Writes thread ids + urls + the full answer text to scratch/demo-threads.json so the storyboard
 * can quote on-screen text exactly rather than from memory.
 *
 * Usage: node scripts/capture-demo-threads.mjs
 */
import { writeFileSync, mkdirSync } from 'node:fs';

const BASE = process.env.MASTRA_URL ?? 'http://localhost:4111';

// Studio scopes a thread to resourceId = the AGENT id — its own requests go to
// .../working-memory?agentId=<arm>&resourceId=<arm>. Capturing under any other resource still
// stores the messages and they still render, but Studio then 403s in a loop on
// threads/subscribe and working-memory ("thread belongs to a different resource"), which is not
// something to point a camera at. Match Studio's convention.
const resourceFor = (armId) => armId;

const ARMS = [
  { id: 'lending-status-baseline-agent', label: 'baseline' },
  { id: 'lending-status-websearch-agent', label: 'websearch' },
  { id: 'lending-status-carver-agent', label: 'carver' },
];
const APPLICANTS = [
  { id: 'CO-1001', state: 'Colorado' },
  { id: 'CA-1001', state: 'California' },
  { id: 'NY-1001', state: 'New York' },
];
const MSG = (id) => `Hi, can you check the status of my loan application? My applicant ID is ${id}.`;

// Deterministic, readable thread ids so a re-run overwrites the same threads instead of piling up
// near-duplicates that make it ambiguous which one the video actually shows.
const threadId = (arm, applicant) => `demo-${arm.label}-${applicant.id.toLowerCase()}`;

// Deterministic ids only help if a re-run REPLACES the thread. Without this the second run appends
// a second exchange to the same thread and the recording shows the question asked twice.
const dropThread = async (arm, thread) => {
  const r = await fetch(`${BASE}/api/memory/threads/${thread}?agentId=${arm.id}`, { method: 'DELETE' });
  if (!r.ok && r.status !== 404) console.warn(`  (could not drop ${thread}: HTTP ${r.status})`);
};

const run = async (arm, applicant) => {
  const thread = threadId(arm, applicant);
  await dropThread(arm, thread);
  const started = Date.now();
  const r = await fetch(`${BASE}/api/agents/${arm.id}/generate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      maxSteps: 8,
      messages: [{ role: 'user', content: MSG(applicant.id) }],
      memory: { thread, resource: resourceFor(arm.id) },
    }),
  });
  if (!r.ok) throw new Error(`${arm.id}/${applicant.id}: HTTP ${r.status} ${await r.text()}`);
  const b = await r.json();
  const text = b.text ?? '';
  const toolNames = (b.steps ?? []).flatMap((s) => (s.toolCalls ?? []).map((c) => c.payload?.toolName ?? c.toolName)).filter(Boolean);
  return {
    arm: arm.label,
    agentId: arm.id,
    applicant: applicant.id,
    state: applicant.state,
    threadId: thread,
    url: `${BASE}/agents/${arm.id}/chat/${thread}`,
    latencySeconds: Math.round((Date.now() - started) / 1000),
    tools: [...new Set(toolNames)],
    totalTokens: b.totalUsage?.totalTokens ?? 0,
    text,
  };
};

const results = [];
for (const applicant of APPLICANTS) {
  for (const arm of ARMS) {
    const out = await run(arm, applicant);
    results.push(out);
    console.log(`${out.applicant}  ${out.arm.padEnd(10)} ${out.latencySeconds}s  ${String(out.totalTokens).padStart(6)} tok  tools=[${out.tools.join(', ')}]`);
    console.log(`    ${out.url}`);
  }
}

mkdirSync('scratch', { recursive: true });
writeFileSync('scratch/demo-threads.json', JSON.stringify(results, null, 2));
console.log(`\nwrote scratch/demo-threads.json (${results.length} threads)`);
console.log('Open any url above in Studio to confirm the thread renders before recording.');
