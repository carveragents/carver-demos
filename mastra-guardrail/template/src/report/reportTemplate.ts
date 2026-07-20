/**
 * §11 — the self-contained HTML report. ONE template literal, `<style>` inlined in
 * `<head>`, no `<link>`, no `<script>`, no `<img>`, no web fonts: it opens correctly
 * via `file://` with the network disabled, which is what makes it shareable with
 * Mastra without them running anything.
 *
 * ── WHAT THIS PAGE IS FOR ───────────────────────────────────────────────────────
 * One question, answered legibly for someone who has never seen this project:
 * **what changes when Carver's data is underneath the agent?** So the page is built
 * as a controlled experiment and reads as one — the same model, the same persona, the
 * same generation settings, the same task, in two columns, with the single difference
 * between them stated as a row in a table rather than as a claim in prose.
 *
 * ── A BLOCK IS THE DESIGNED OUTCOME (orchestrator D28.5) ────────────────────────
 * Mastra wraps output processors in a workflow, so a CORRECT `abort()` — the
 * guardrail doing exactly its job — also emits `[WORKFLOW] Error executing step …`
 * plus a stack trace to stderr. **The guardrail working correctly looks like a
 * crash**, and nobody watching a demo reads the source to discover the red text was
 * the point. This page cannot silence Mastra's stderr and does not try. What it does
 * instead is make the block the headline: the verdict stamp is the first thing on the
 * page, it is rendered from `report.outcome` (the workflow's own top-level field, not
 * a hand-typed string), and the copy beside it names the stack trace and says plainly
 * that it is the success path.
 *
 * ── WHAT THIS PAGE MUST NOT CLAIM (orchestrator D29.2, D22) ─────────────────────
 * 1. **No citation-fabrication detection on the template side.** Citation fabrication
 *    IS detected — in `prep/`, at curation time, where the URL resolver lives. The
 *    template ships no resolver, so nothing here re-derives it, and nothing here says
 *    it does. The citation below is Carver's own ground truth, rendered so a reader
 *    can click it; it is not a claim about anything the baseline cited.
 * 2. **"Auditable", never "reproducible"** (D22 — the replay harness was cut). The
 *    honest claim is that the run's decision is on disk and can be read, and that is
 *    the claim the colophon makes.
 * An accurate narrow claim beats an impressive broad one a careful reader can
 * falsify — and this page's audience reads carefully.
 */
import {
  MAX_OUTPUT_TOKENS,
  MODEL_CUTOFF,
  MODEL_ID,
  REASONING_EFFORT,
  SNAPSHOT_DATE,
} from "../config";
import type { ComparisonReport, GuardedResult } from "../workflows/compareWorkflow";

/** The blocked arm of §10's discriminated union. */
type BlockedGuardedResult = Extract<GuardedResult, { blocked: true }>;

/**
 * A `ComparisonReport` whose guarded arm is known to have blocked.
 *
 * The renderer takes THIS, not `ComparisonReport`, so §11's "a demo report is only
 * ever generated from a run that really blocked" is enforced by the TYPE SYSTEM on
 * top of `generateHtmlReport`'s runtime throw — a caller cannot reach the template
 * with a delivered run even by accident. It is also why the fields below need no
 * null-checks: `blocked_draft`, `reason` and `record` are non-null on this branch by
 * construction.
 */
export type BlockedComparisonReport = Omit<ComparisonReport, "guarded"> & {
  guarded: BlockedGuardedResult;
};

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

/**
 * The ONE escaping helper, applied to every interpolated value without exception.
 *
 * Every field this template renders — the two drafts, the tripwire reason, the record
 * title, the regulator name, the citation name — is LLM-generated or corpus-sourced
 * text being interpolated into an HTML document. None of it is trusted markup, and a
 * demo whose entire subject is compliance must not be the thing that ships an
 * injection. A single pass over one character class, so no escape is ever
 * double-escaped by a later replacement.
 */
export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, character => HTML_ESCAPES[character]);
}

/**
 * The only value that lands inside an `href`, and the only one that gets a check
 * beyond escaping. §5's schema already guarantees a URL (`z.string().url()`), so this
 * is a defensive re-check one hop from that type system — cheap, and it closes the
 * one place where corpus-sourced data becomes something a reader is invited to click.
 * Throws rather than degrading: a report that silently dropped its citation would
 * still look like a finished demo.
 */
function safeHref(url: string): string {
  if (!/^https?:\/\//i.test(url)) {
    throw new Error(
      `refusing to render citation URL ${JSON.stringify(url)} — only http:// and https:// are `
      + `emitted into an href, and a demo about real, clickable citations must not be the thing `
      + `that ships a javascript: link`,
    );
  }
  return escapeHtml(url);
}

/** `null` compliance dates are legal on a `ClearedRecord`, so absence must render as
 *  absence rather than as an empty cell a reader would take for a missing field. */
const orDash = (value: string | null): string =>
  value === null ? `<span class="absent">none recorded</span>` : escapeHtml(value);

/**
 * The page's whole visual system, inlined.
 *
 * NO WEB FONTS AND NO REMOTE ANYTHING (§11). Every family below is a local stack, so
 * the page renders identically with the network off — which is the condition it is
 * actually shared under. The look is a printed evidence dossier: ink on warm paper,
 * hairline rules, one stamp, two columns. It is deliberately not a dashboard; the
 * artifact is a document about what happened, and it should read as one on screen and
 * on paper alike.
 */
const STYLE = `
:root {
  --paper: #f2eee4;
  --paper-raised: #fbfaf6;
  --ink: #17150e;
  --ink-soft: #5d574a;
  --ink-faint: #8b8474;
  --rule: #d8d0bd;
  --rule-strong: #17150e;
  /* Two signal colours, used for one thing each and never decoratively.
     risk  = what reached the caller unchecked.
     guard = what Carver's data stopped. */
  --risk: #a32d12;
  --risk-wash: #f6e6df;
  --guard: #0f5545;
  --guard-wash: #e2ece6;
  --font-display: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", "JetBrains Mono", "IBM Plex Mono", Menlo, Consolas, monospace;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-display);
  font-size: 17px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

.sheet {
  max-width: 1100px;
  margin: 0 auto;
  padding: 4rem 2rem 3rem;
}

/* ── entrance: one orchestrated load, then it is a document ─────────────── */
/* nth-CHILD, not nth-of-type: .sheet's children are header/section/…/footer, and
   nth-of-type would restart the count at each element type — giving the header, the
   first section and the footer the same delay. */
.reveal { animation: rise 0.5s cubic-bezier(0.2, 0.7, 0.3, 1) both; }
.reveal:nth-child(1) { animation-delay: 0.02s; }
.reveal:nth-child(2) { animation-delay: 0.09s; }
.reveal:nth-child(3) { animation-delay: 0.15s; }
.reveal:nth-child(4) { animation-delay: 0.21s; }
.reveal:nth-child(5) { animation-delay: 0.27s; }
@keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) {
  .reveal, .stamp { animation: none; }
}

/* ── masthead ───────────────────────────────────────────────────────────── */
.eyebrow {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin: 0 0 1.6rem;
  padding-bottom: 0.9rem;
  border-bottom: 1px solid var(--rule-strong);
}
h1 {
  font-size: clamp(2.1rem, 5.2vw, 3.6rem);
  line-height: 1.03;
  letter-spacing: -0.022em;
  font-weight: 400;
  margin: 0 0 1.1rem;
  max-width: 20ch;
}
h1 em { font-style: italic; }
.standfirst {
  font-size: 1.16rem;
  color: var(--ink-soft);
  max-width: 62ch;
  margin: 0;
}
.standfirst strong { color: var(--ink); font-weight: 600; }

/* ── verdict ────────────────────────────────────────────────────────────── */
.verdict {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2.4rem;
  align-items: start;
  margin: 3.2rem 0;
  padding: 2rem 0;
  border-top: 3px double var(--rule-strong);
  border-bottom: 3px double var(--rule-strong);
}
.stamp {
  border: 3px double var(--guard);
  color: var(--guard);
  padding: 0.75rem 1.5rem 0.6rem;
  text-align: center;
  transform: rotate(-3.5deg);
  animation: slam 0.45s cubic-bezier(0.2, 1.5, 0.4, 1) 0.42s both;
  white-space: nowrap;
}
@keyframes slam {
  from { opacity: 0; transform: rotate(-3.5deg) scale(1.5); }
  to   { opacity: 1; transform: rotate(-3.5deg) scale(1); }
}
.stamp__word {
  display: block;
  font-family: var(--font-mono);
  font-size: clamp(1.6rem, 4vw, 2.5rem);
  font-weight: 700;
  letter-spacing: 0.14em;
  line-height: 1;
}
.stamp__sub {
  display: block;
  font-family: var(--font-mono);
  font-size: 0.6rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  margin-top: 0.45rem;
  color: var(--guard);
  opacity: 0.85;
}
.verdict h2 {
  font-size: 1.5rem;
  font-weight: 400;
  letter-spacing: -0.01em;
  margin: 0 0 0.7rem;
}
.verdict p { margin: 0 0 0.8rem; color: var(--ink-soft); max-width: 62ch; }
.verdict p:last-child { margin-bottom: 0; }
.aside {
  font-size: 0.9rem;
  border-left: 2px solid var(--rule);
  padding-left: 1rem;
}
code {
  font-family: var(--font-mono);
  font-size: 0.85em;
  background: var(--paper-raised);
  border: 1px solid var(--rule);
  padding: 0.05em 0.35em;
  white-space: nowrap;
}

/* ── section furniture ──────────────────────────────────────────────────── */
.section-label {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin: 0 0 1.1rem;
}

/* ── the controlled-experiment table ────────────────────────────────────── */
.control { margin: 3rem 0; }
table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-mono);
  font-size: 0.82rem;
}
thead th {
  text-align: left;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-size: 0.66rem;
  color: var(--ink-faint);
  padding: 0 1rem 0.7rem 0;
  border-bottom: 1px solid var(--rule-strong);
}
tbody td, tbody th {
  text-align: left;
  font-weight: 400;
  padding: 0.7rem 1rem 0.7rem 0;
  border-bottom: 1px solid var(--rule);
  vertical-align: top;
}
tbody th { color: var(--ink-faint); white-space: nowrap; }
tr.difference td, tr.difference th {
  background: var(--guard-wash);
  border-bottom: 1px solid var(--guard);
  font-weight: 700;
}
tr.difference .marker { color: var(--guard); font-weight: 700; }
.same { color: var(--ink-faint); }

/* ── the two arms ───────────────────────────────────────────────────────── */
.arms {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin: 3rem 0;
}
.arm {
  background: var(--paper-raised);
  border: 1px solid var(--rule);
  border-top: 4px solid var(--rule-strong);
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
}
.arm--baseline { border-top-color: var(--risk); }
.arm--guarded { border-top-color: var(--guard); }
.arm__kicker {
  font-family: var(--font-mono);
  font-size: 0.66rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin: 0 0 0.35rem;
}
.arm__verdict {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin: 0 0 1.2rem;
}
.arm--baseline .arm__verdict { color: var(--risk); }
.arm--guarded .arm__verdict { color: var(--guard); }
.draft {
  font-family: var(--font-mono);
  font-size: 0.82rem;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0 0 1.2rem;
  padding: 1.1rem;
  background: var(--paper);
  border: 1px solid var(--rule);
  flex: 1;
}
.arm--baseline .draft { border-left: 3px solid var(--risk); }
.arm--guarded .draft { border-left: 3px solid var(--guard); }
.arm__note {
  font-size: 0.9rem;
  color: var(--ink-soft);
  margin: 0;
  padding-top: 0.9rem;
  border-top: 1px solid var(--rule);
}
.arm__note strong { color: var(--ink); }

/* ── the obligation ─────────────────────────────────────────────────────── */
.obligation {
  margin: 3rem 0;
  padding: 2rem;
  background: var(--guard-wash);
  border: 1px solid var(--guard);
}
.obligation h2 {
  font-size: 1.7rem;
  font-weight: 400;
  line-height: 1.2;
  letter-spacing: -0.015em;
  margin: 0 0 1.5rem;
  max-width: 46ch;
}
.obligation .section-label { color: var(--guard); }
dl {
  margin: 0;
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.1rem 1.5rem;
}
dt {
  font-family: var(--font-mono);
  font-size: 0.64rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--guard);
  padding: 0.65rem 0;
  border-top: 1px solid var(--guard);
  white-space: nowrap;
}
dd {
  font-family: var(--font-mono);
  font-size: 0.84rem;
  margin: 0;
  padding: 0.65rem 0;
  border-top: 1px solid var(--guard);
  word-break: break-word;
}
dd.date { font-size: 1rem; font-weight: 700; }
.absent { color: var(--ink-faint); font-style: italic; }
a {
  color: var(--guard);
  text-underline-offset: 3px;
  text-decoration-thickness: 1px;
}
a:hover { background: var(--guard); color: var(--paper-raised); text-decoration: none; }

/* ── colophon ───────────────────────────────────────────────────────────── */
.colophon {
  margin-top: 3.5rem;
  padding-top: 1.2rem;
  border-top: 1px solid var(--rule-strong);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  line-height: 1.75;
  color: var(--ink-faint);
}
.colophon .provenance { color: var(--ink-soft); }
.colophon p { margin: 0 0 0.5rem; max-width: 84ch; }

/* ── narrow ─────────────────────────────────────────────────────────────── */
@media (max-width: 820px) {
  .sheet { padding: 2.5rem 1.25rem; }
  .arms { grid-template-columns: 1fr; }
  .verdict { grid-template-columns: 1fr; gap: 1.5rem; }
  dl { grid-template-columns: 1fr; gap: 0; }
  dd { border-top: 0; padding-top: 0; }
  table { font-size: 0.74rem; }
}

/* ── print: it is a document, so it should print like one ───────────────── */
@media print {
  body { background: #fff; }
  .sheet { padding: 0; max-width: none; }
  .reveal, .stamp { animation: none; }
  .arm, .obligation, .verdict { break-inside: avoid; }
}
`;

/**
 * The rows of the controlled-experiment table — every knob both arms share, and then
 * the one that differs.
 *
 * WHY THIS TABLE EXISTS AT ALL. Goal #9's fatal case is a comparison that differs in
 * something other than "whether Carver data gates the output", because such a demo
 * *looks like success*. Stating "same model, same config" in prose asks the reader to
 * take our word for it. Printing every shared setting and marking the single
 * difference lets them check it in four seconds, which is the only version of this
 * claim worth making to an audience that builds agents for a living.
 */
const CONTROL_ROWS: readonly { label: string; baseline: string; guarded: string; differs?: true }[] = [
  { label: "Model", baseline: MODEL_ID, guarded: MODEL_ID },
  { label: "Reasoning effort", baseline: REASONING_EFFORT, guarded: REASONING_EFFORT },
  { label: "Max output tokens", baseline: String(MAX_OUTPUT_TOKENS), guarded: String(MAX_OUTPUT_TOKENS) },
  { label: "Instructions", baseline: "the same persona, verbatim", guarded: "the same persona, verbatim" },
  { label: "Task prompt", baseline: "the same prompt, verbatim", guarded: "the same prompt, verbatim" },
  {
    label: "Carver data",
    baseline: "none",
    guarded: "CarverGuardrail — a Mastra outputProcessor over Carver's cleared set",
    differs: true,
  },
];

const renderControlRow = (row: (typeof CONTROL_ROWS)[number]): string => {
  const cell = (value: string): string =>
    row.differs ? escapeHtml(value) : `<span class="same">${escapeHtml(value)}</span>`;
  return `
        <tr${row.differs ? ` class="difference"` : ""}>
          <th scope="row">${escapeHtml(row.label)}${row.differs ? ` <span class="marker">←</span>` : ""}</th>
          <td>${cell(row.baseline)}</td>
          <td>${cell(row.guarded)}</td>
        </tr>`;
};

/**
 * The whole page, from one real run.
 *
 * Takes a `BlockedComparisonReport`: §11's "never hand-authored, only ever from a run
 * that really blocked" is a type here, not a convention. Every dynamic value is
 * escaped through `escapeHtml`; the one `href` additionally goes through `safeHref`.
 */
export function renderReportHtml(report: BlockedComparisonReport): string {
  const { baseline, guarded } = report;
  const { record } = guarded;
  const alsoViolated = guarded.violated_obligation_ids.slice(1);

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Carver × Mastra — the same agent, with and without Carver's data</title>
<style>${STYLE}</style>
</head>
<body>
<main class="sheet">

  <header class="reveal">
    <p class="eyebrow">Carver × Mastra · compliance guardrail · generated from a real run</p>
    <h1>The same agent, twice.<br><em>Once with Carver's data underneath it.</em></h1>
    <p class="standfirst">Both columns below are the <strong>same model</strong>, given the
      <strong>same instructions</strong>, the <strong>same generation settings</strong> and the
      <strong>same task</strong>. The only difference is that the right-hand agent carries a Mastra
      <code>outputProcessor</code> holding Carver's cleared set of real 2026 regulatory obligations.
      One of these drafts was checked against a real obligation before delivery. The other was
      not.</p>
  </header>

  <section class="verdict reveal">
    <div class="stamp" role="img" aria-label="Outcome: ${escapeHtml(report.outcome)}">
      <span class="stamp__word">${escapeHtml(report.outcome)}</span>
      <span class="stamp__sub">by carver guardrail</span>
    </div>
    <div>
      <h2>This is the designed outcome, not an error.</h2>
      <p>The guarded agent produced its draft, the processor checked it against the obligations
        Carver's data says apply to this firm, and it called <code>abort()</code> before a word
        reached the caller. The workflow run itself completed successfully — the tripwire is
        contained inside the step, so the baseline branch beside it ran to completion untouched.</p>
      <p class="aside">Watch stderr while this runs: Mastra executes output processors inside a
        workflow, so a correct <code>abort()</code> also prints
        <code>[WORKFLOW] Error executing step …</code> and a stack trace. That red text is the
        guardrail firing. This page is what actually happened.</p>
    </div>
  </section>

  <section class="control reveal">
    <p class="section-label">The controlled experiment — check it yourself</p>
    <table>
      <thead>
        <tr>
          <th scope="col"></th>
          <th scope="col">Without Carver data</th>
          <th scope="col">With Carver data</th>
        </tr>
      </thead>
      <tbody>${CONTROL_ROWS.map(renderControlRow).join("")}
      </tbody>
    </table>
  </section>

  <section class="arms reveal">
    <article class="arm arm--baseline">
      <p class="arm__kicker">Without Carver data</p>
      <p class="arm__verdict">DELIVERED TO THE CALLER</p>
      <p class="draft">${escapeHtml(baseline.text)}</p>
      <p class="arm__note">Shipped exactly as drafted. <strong>Nothing inspected it</strong>, and no
        prompt could have helped: the obligation below was published after this model's knowledge
        cutoff, so it is not in there to recall.</p>
    </article>
    <article class="arm arm--guarded">
      <p class="arm__kicker">With Carver data</p>
      <p class="arm__verdict">BLOCKED BEFORE DELIVERY</p>
      <p class="draft">${escapeHtml(guarded.blocked_draft)}</p>
      <p class="arm__note"><strong>The same agent drafted this and never got to send it.</strong>
        Caught by <code>${escapeHtml(guarded.processorId)}</code>: ${escapeHtml(guarded.reason)}</p>
    </article>
  </section>

  <section class="obligation reveal">
    <p class="section-label">The obligation that fired</p>
    <h2>${escapeHtml(record.title)}</h2>
    <dl>
      <dt>Regulator</dt>
      <dd>${escapeHtml(record.regulator_name)}</dd>
      <dt>Compliance date</dt>
      <dd class="date">${orDash(record.compliance_date)}</dd>
      <dt>Citation</dt>
      <dd><a href="${safeHref(record.citation.url)}">${escapeHtml(record.citation.name)}</a><br>
        ${escapeHtml(record.citation.url)}</dd>
      <dt>Carver record</dt>
      <dd>${escapeHtml(record.id)}${alsoViolated.length
        ? ` · also violated: ${escapeHtml(alsoViolated.join(", "))}`
        : ""}</dd>
    </dl>
  </section>

  <footer class="colophon">
    <p class="provenance">Baseline model: ${escapeHtml(MODEL_ID)} · Knowledge cutoff: ${escapeHtml(MODEL_CUTOFF)} · Carver snapshot: ${escapeHtml(SNAPSHOT_DATE)}</p>
    <p>The baseline is deliberately the strongest available model, not an old one chosen to make
      the gap look bigger. Every shipped record is dated after that cutoff, human-reviewed, and
      carries recorded evidence of how the baseline failed it.</p>
    <p>One run is an anecdote, and this page does not ask you to take it for more than that: the
      left-hand draft was never judged, because nothing was there to judge it. <code>npm test</code>
      asks the measurable version of the question across the whole cleared set — how often each arm
      delivers a draft that violates the obligation Carver matched — and prints it as one paired
      table.</p>
    <p>This run is <strong>auditable</strong>: the guardrail appends every enforcement decision —
      the obligations it judged violated, the severity Carver's own data assigned, and the action
      it took — to <code>.mastra/output/guardrail-audit.jsonl</code>. The page you are reading was
      generated from the run's own output, never hand-authored.</p>
  </footer>

</main>
</body>
</html>
`;
}
