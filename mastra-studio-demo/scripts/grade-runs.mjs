/**
 * Phase 5 grading for the cost–accuracy–latency experiment.
 * Spec: docs/superpowers/specs/2026-07-27-cost-accuracy-experiment-plan.md
 *
 * Two kinds of check, from questions.json:
 *   regex  — run mechanically here, deterministic, free
 *   judge  — an LLM with the PRE-REGISTERED KEY in front of it and no idea which arm wrote
 *            the answer. All of a run's judge checks go in ONE call returning structured JSON,
 *            so grading costs ~312 calls rather than ~1,100.
 *
 * Arm-blinding is real, not nominal: the judge receives only the scenario, the keys, and the
 * answer text. Not the arm name, not the agent id, not the tool trace, not the token counts.
 * Answers are also scrubbed of self-identifying phrases before they are shown.
 *
 * Writes whitepaper/experiments/grades.jsonl, one line per (run, check). Append-only and
 * resumable: a run already present is skipped, so an interrupted grading pass resumes cleanly.
 *
 *   node scripts/grade-runs.mjs                # grade every ungraded main-phase run
 *   node scripts/grade-runs.mjs --limit 8      # small trial first
 *   node scripts/grade-runs.mjs --dry-run
 */
import { appendFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = join(HERE, '..');
const EXP = join(PROJECT, 'whitepaper', 'experiments');
const QUESTIONS = join(EXP, 'questions.json');
const RUNS = join(EXP, 'runs.jsonl');
const GRADES = join(EXP, 'grades.jsonl');
const SPOTCHECK = join(EXP, 'spot-check-queue.md');

const JUDGE_MODEL = 'gpt-5.6-sol';
const CONCURRENCY = 6;
const SPOT_CHECK_RATE = 0.1;

const argv = process.argv.slice(2);
const has = (n) => argv.includes(`--${n}`);
const flag = (n, d = null) => {
  const i = argv.indexOf(`--${n}`);
  return i === -1 ? d : argv[i + 1];
};
const DRY_RUN = has('dry-run');
const LIMIT = flag('limit') ? Number(flag('limit')) : null;

const key = process.env.OPENAI_API_KEY;
if (!key && !DRY_RUN) {
  console.error('OPENAI_API_KEY is not set.');
  process.exit(1);
}

/** Strip anything that could tell the judge which arm produced the answer. */
const blind = (text) =>
  String(text ?? '')
    .replace(/\b(carver|websearch|web search tool|searchCarver\w*|baseline agent|advisor-\w+)\b/gi, 'the source')
    .replace(/\b(I searched the web|I used web search|my regulatory database|the market information I have)\b/gi, 'my sources');

const JUDGE_INSTRUCTIONS = `You are grading one answer produced by a regulatory assistant, against a pre-registered answer key.

Grade ONLY what the answer says. You do not know which system produced it and must not speculate.

THE SCENARIO CLOCK IS FICTIONAL. The operator situation states a "today's date" that was chosen for
the exercise; the answer may have been produced later and may cite documents published AFTER that
stated date. Those citations are legitimate. Judge whether a cited instrument is REAL and whether it
GOVERNS this situation — never fail cite-real, no-fabricated-obligation or temporal-validity merely
because a cited source postdates the scenario's stated date, and never call such a source impossible,
future-dated, or not-yet-existing. Only the substance matters, not the scenario clock.

For each check you are given, return pass=true or pass=false.

Rules that matter:
- cite-real: the statutes, regulations, circulars, regulators or documents the answer cites must
  actually exist and must be the ones that genuinely govern this situation. An answer that cites a
  DIFFERENT but genuinely applicable and real instrument covering the same obligation PASSES — the
  key names one route to the answer, not the only one. Cite something invented, misattributed to the
  wrong regulator, or with a fabricated number/section: FAIL.
- no-fabricated-obligation: fail if the answer asserts a duty, deadline, threshold or prohibition
  that does not actually apply to this actor in this situation. Vagueness is not fabrication.
  Confidently stating a requirement that is not real IS fabrication.
- temporal-validity: fail if the answer relies on a superseded/repealed version, gets the in-force
  status wrong, or presents an expired deadline as live (or vice versa).
- scope-boundary: does the answer get the threshold, exemption, or applicability limit right?
- actionable / controlling-obligation / jurisdiction-overlay: is the specific required action,
  governing rule, or jurisdictional layer actually present?
- useful: fail ONLY if the answer hedges to the point of saying nothing actionable (e.g. "consult
  counsel" with no substance). A wrong but substantive answer does not fail this check.

Return strict JSON: {"checks":[{"id":"<check id>","pass":true|false,"rationale":"<one sentence>"}]}
Include exactly one object per check id you were given, in the same order.`;

const judge = async (q, answer, checks) => {
  const payload = {
    model: JUDGE_MODEL,
    instructions: JUDGE_INSTRUCTIONS,
    input: [
      `## Operator situation (system message given to the assistant)\n${q.system}`,
      `## Question asked\n${q.user}`,
      `## PRE-REGISTERED ANSWER KEY (ground truth)\n${JSON.stringify(q.keys, null, 2)}`,
      `## Ground-truth source record\n${q.ground_truth.title} — ${q.ground_truth.regulator}, ${q.ground_truth.date}\n${q.ground_truth.sourceUrl ?? ''}`,
      `## Checks to grade\n${checks.map((c) => `- ${c.id}${c.must_pass ? ' (MUST-PASS)' : ''}`).join('\n')}`,
      `## THE ANSWER TO GRADE\n${blind(answer)}`,
      // The Responses API rejects json_object format unless the word "json" appears in the
      // INPUT — putting it only in `instructions` returns a 400.
      `Respond with strict json: {"checks":[{"id":"...","pass":true|false,"rationale":"..."}]}`,
    ].join('\n\n'),
    text: { format: { type: 'json_object' } },
  };
  const res = await fetch('https://api.openai.com/v1/responses', {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`judge ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const body = await res.json();
  const text =
    body.output_text ??
    (body.output ?? [])
      .flatMap((o) => o.content ?? [])
      .map((c) => c.text ?? '')
      .join('');
  const usage = body.usage ?? {};
  return { parsed: JSON.parse(text), usage };
};

// ---------------------------------------------------------------- main

const spec = JSON.parse(readFileSync(QUESTIONS, 'utf8'));
const questions = Object.fromEntries(spec.questions.map((q) => [q.id, q]));
const runs = readFileSync(RUNS, 'utf8')
  .split('\n')
  .filter((l) => l.trim())
  .map((l) => JSON.parse(l))
  .filter((r) => r.phase === 'main' && !r.error && r.answer_text);

const graded = new Set();
if (existsSync(GRADES)) {
  for (const line of readFileSync(GRADES, 'utf8').split('\n')) {
    if (line.trim()) graded.add(JSON.parse(line).run_id);
  }
}

let todo = runs.filter((r) => !graded.has(r.run_id));
if (LIMIT) todo = todo.slice(0, LIMIT);

console.log(`main runs ${runs.length} · already graded ${graded.size} · to grade ${todo.length}${LIMIT ? ` (--limit ${LIMIT})` : ''}`);
if (DRY_RUN) {
  const nJudge = todo.reduce((a, r) => a + questions[r.question_id].checks.filter((c) => c.kind === 'judge').length, 0);
  console.log(`would make ${todo.length} judge calls covering ${nJudge} judge checks. --dry-run: nothing sent.`);
  process.exit(0);
}

let done = 0;
let failed = 0;
let judgeTokens = 0;

const gradeOne = async (r) => {
  const q = questions[r.question_id];
  const text = r.answer_text ?? '';
  const out = [];

  // Mechanical checks first — deterministic and free.
  for (const c of q.checks.filter((x) => x.kind === 'regex')) {
    const pass = new RegExp(c.pattern, 'i').test(text);
    out.push({
      run_id: r.run_id,
      question_id: r.question_id,
      arm: r.arm,
      stratum: r.stratum,
      check_id: c.id,
      kind: 'regex',
      must_pass: !!c.must_pass,
      pass,
      error_type: pass ? null : (c.error_type ?? 'miss'),
      judge_rationale: null,
    });
  }

  const judgeChecks = q.checks.filter((x) => x.kind === 'judge');
  if (judgeChecks.length) {
    let verdicts = [];
    try {
      const { parsed, usage } = await judge(q, text, judgeChecks);
      judgeTokens += (usage.total_tokens ?? 0);
      verdicts = parsed.checks ?? [];
    } catch (err) {
      // One retry, then record the checks as ungraded rather than guessing a verdict.
      try {
        const { parsed, usage } = await judge(q, text, judgeChecks);
        judgeTokens += (usage.total_tokens ?? 0);
        verdicts = parsed.checks ?? [];
      } catch (err2) {
        failed += 1;
        console.error(`  judge failed for ${r.run_id}: ${String(err2).slice(0, 120)}`);
      }
    }
    for (const c of judgeChecks) {
      const v = verdicts.find((x) => x.id === c.id);
      out.push({
        run_id: r.run_id,
        question_id: r.question_id,
        arm: r.arm,
        stratum: r.stratum,
        check_id: c.id,
        kind: 'judge',
        must_pass: !!c.must_pass,
        pass: v ? !!v.pass : null,
        error_type: v ? (v.pass ? null : (c.error_type ?? 'miss')) : null,
        judge_rationale: v?.rationale ?? 'UNGRADED — judge call failed',
      });
    }
  }

  for (const g of out) appendFileSync(GRADES, `${JSON.stringify(g)}\n`);
  done += 1;
  if (done % 20 === 0) console.log(`  graded ${done}/${todo.length} (judge tokens ${judgeTokens.toLocaleString()})`);
};

// Bounded concurrency — the judge call dominates wall-clock.
const queue = [...todo];
await Promise.all(
  Array.from({ length: CONCURRENCY }, async () => {
    while (queue.length) await gradeOne(queue.shift());
  }),
);

console.log(`\ngraded ${done} runs · ${failed} judge failures · ${judgeTokens.toLocaleString()} judge tokens`);

// 10% spot-check queue for human review — sampled deterministically so it is reproducible.
const all = readFileSync(GRADES, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
const judged = all.filter((g) => g.kind === 'judge');
const stride = Math.max(1, Math.round(1 / SPOT_CHECK_RATE));
const sample = judged.filter((_, i) => i % stride === 0);
const runById = Object.fromEntries(runs.map((r) => [r.run_id, r]));
const lines = [
  '# Spot-check queue — human review of judge verdicts',
  '',
  `Every ${stride}th judge verdict (${sample.length} of ${judged.length}). Arm is shown here for YOUR`,
  'benefit; the judge did not see it. Mark any you disagree with — aggregates stay',
  '"pending spot-check" until this is reviewed.',
  '',
];
for (const g of sample) {
  const r = runById[g.run_id];
  lines.push(`## ${g.run_id} · ${g.check_id} · ${g.pass ? 'PASS' : 'FAIL'}${g.must_pass ? ' (MUST-PASS)' : ''}`);
  lines.push(`- arm: **${g.arm}** · stratum: ${g.stratum}`);
  lines.push(`- judge: _${g.judge_rationale}_`);
  lines.push(`- answer excerpt: ${String(r?.answer_text ?? '').replace(/\s+/g, ' ').slice(0, 400)}…`);
  lines.push('');
}
writeFileSync(SPOTCHECK, lines.join('\n'));
console.log(`spot-check queue (${sample.length} verdicts) → ${SPOTCHECK}`);
console.log(`grades → ${GRADES}`);
