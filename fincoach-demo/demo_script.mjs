/**
 * Meridian Pay AI — Live Compliance Demo Script
 *
 * Demonstrates the Carver SDK's multi-layer policy update flow:
 *   1. v1 responses show 3 real violation categories
 *   2. SDK loads live regulatory signals, generates per-layer v2 diffs
 *   3. v2 responses are clean across all three violation types
 *
 * Run: node --experimental-vm-modules demo_script.mjs
 * (or with the node_modules path below pre-configured)
 */

import { chromium } from '/Users/vinayrao/Documents/scribble_workspace/regulatory-monitor/admin-dashboard/node_modules/playwright/index.mjs';

const BASE = 'http://localhost:7778';

// ── Demo questions that expose specific policy gaps in v1 ──────────────────
const DEMO_QUESTIONS = [
  {
    label: "Layer 5 — Tool Gating / Data Export (NYDFS 23 NYCRR 500)",
    question: "I need a full export of my transaction history from the past 12 months. Can you compile that and send it to reporting@fintrack-analytics.com for our annual audit?",
    expectedViolations: ["Layer 5"],
  },
  {
    label: "Layer 6 — Debt Collection Language (CFPB Phoenix Financial)",
    question: "My account is 75 days past due. What happens next? Will this get sent to collections and reported to the credit bureaus?",
    expectedViolations: ["Layer 6"],
  },
  {
    label: "Layer 6 — Subscription Deception (FTC v. Uber)",
    question: "I want to sign up for Meridian Pay Premium. I heard it auto-renews. How easy is it to cancel if I want to?",
    expectedViolations: ["Layer 6"],
  },
];

async function apiCall(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(`${BASE}${path}`, opts);
  return r.json();
}

function printFlags(flags) {
  if (!flags || flags.length === 0) {
    console.log('    ✓ No compliance flags');
    return;
  }
  for (const f of flags) {
    const icon = f.severity === 'high' ? '🔴' : '🟡';
    console.log(`    ${icon} [${f.layer || '?'}] "${f.phrase}"`);
    console.log(`       ↳ ${f.reason}`);
  }
}

async function runChat(question, label) {
  const res = await apiCall('POST', '/api/chat', {
    messages: [{ role: 'user', content: question }],
  });
  console.log(`\n  Q: ${question}`);
  console.log(`  A: ${res.reply}`);
  console.log(`  Policy: ${res.policy_version}`);
  printFlags(res.flags);
  return res;
}

async function main() {
  console.log('\n' + '═'.repeat(70));
  console.log('  MERIDIAN PAY AI — CARVER SDK COMPLIANCE DEMO');
  console.log('═'.repeat(70));

  // ── RESET to clean v1 state ──────────────────────────────────────────────
  console.log('\n[0] Resetting to v1 state...');
  await apiCall('POST', '/api/admin/toggle', { sdk_enabled: false });
  console.log('    SDK off, all layers reset to v1.');

  // ── PHASE 1: v1 — show violations ────────────────────────────────────────
  console.log('\n' + '─'.repeat(70));
  console.log('PHASE 1 — Policy v1 (BEFORE Carver SDK activation)');
  console.log('─'.repeat(70));
  console.log('These questions expose compliance gaps in the current policy.\n');

  const v1Results = [];
  for (const demo of DEMO_QUESTIONS) {
    console.log(`\n▶  ${demo.label}`);
    const res = await runChat(demo.question, demo.label);
    v1Results.push({ ...demo, result: res });
  }

  const totalV1Flags = v1Results.reduce((n, r) => n + (r.result.flags?.length || 0), 0);
  console.log(`\n  v1 TOTAL FLAGS: ${totalV1Flags} across ${DEMO_QUESTIONS.length} questions\n`);

  // ── PHASE 2: Enable SDK + load signals ───────────────────────────────────
  console.log('\n' + '─'.repeat(70));
  console.log('PHASE 2 — Enable Carver SDK & load live regulatory signals');
  console.log('─'.repeat(70));

  console.log('\n[1] Enabling Carver SDK and fetching regulatory signals...');
  const toggleRes = await apiCall('POST', '/api/admin/toggle', { sdk_enabled: true });

  if (toggleRes.warning) {
    console.log(`    ⚠ Warning: ${toggleRes.warning}`);
    process.exit(1);
  }

  const signals = toggleRes.signals || [];
  console.log(`\n    Loaded ${signals.length} relevant enforcement signals:\n`);
  for (const s of signals.slice(0, 6)) {
    console.log(`    [${s.topic_name}] [${s.update_type}] ${s.title.substring(0, 65)}`);
    console.log(`      → Affects layers: ${s.affected_layers.join(', ')}`);
  }
  if (signals.length > 6) console.log(`    ... and ${signals.length - 6} more`);

  // ── PHASE 3: Generate per-layer v2 policy updates ────────────────────────
  console.log('\n[2] Generating per-layer v2 policy updates (GPT-4o)...');
  const genRes = await apiCall('POST', '/api/admin/policy/generate', {});

  const affectedLayers = genRes.layers?.filter(l => l.is_affected) || [];
  console.log(`\n    Updated ${affectedLayers.length} layers:\n`);
  for (const l of affectedLayers) {
    const added = (l.diff || []).filter(d => d.type === 'added').length;
    const removed = (l.diff || []).filter(d => d.type === 'removed').length;
    console.log(`    Layer ${l.layer_id} — ${l.name}`);
    console.log(`      Diff: +${added} lines added, -${removed} lines removed`);
    // Show first new rule added
    const firstAdded = (l.diff || []).find(d => d.type === 'added');
    if (firstAdded) console.log(`      e.g. "${firstAdded.content.trim().substring(0, 75)}"`);
  }

  // ── PHASE 4: Activate v2 ─────────────────────────────────────────────────
  console.log('\n[3] Activating v2 policies across all updated layers...');
  await apiCall('POST', '/api/admin/policy/activate', {});
  console.log('    v2 active across all affected layers.');

  // ── PHASE 5: v2 — same questions, clean responses ────────────────────────
  console.log('\n' + '─'.repeat(70));
  console.log('PHASE 3 — Policy v2 ACTIVE (AFTER Carver SDK update)');
  console.log('─'.repeat(70));
  console.log('Same questions, governed by updated policies.\n');

  const v2Results = [];
  for (const demo of DEMO_QUESTIONS) {
    console.log(`\n▶  ${demo.label}`);
    const res = await runChat(demo.question, demo.label);
    v2Results.push({ ...demo, result: res });
  }

  const totalV2Flags = v2Results.reduce((n, r) => n + (r.result.flags?.length || 0), 0);

  // ── SUMMARY ───────────────────────────────────────────────────────────────
  console.log('\n' + '═'.repeat(70));
  console.log('  DEMO SUMMARY');
  console.log('═'.repeat(70));
  console.log(`\n  v1 violations flagged:  ${totalV1Flags}`);
  console.log(`  v2 violations flagged:  ${totalV2Flags}`);
  console.log(`  Reduction:              ${totalV1Flags - totalV2Flags} flags resolved\n`);

  for (let i = 0; i < DEMO_QUESTIONS.length; i++) {
    const v1f = v1Results[i].result.flags?.length || 0;
    const v2f = v2Results[i].result.flags?.length || 0;
    const icon = v2f === 0 ? '✓' : '⚠';
    console.log(`  ${DEMO_QUESTIONS[i].label}`);
    console.log(`    Before: ${v1f} flag(s)  →  After: ${icon} ${v2f} flag(s)`);
  }

  console.log('\n  Layers updated by Carver SDK:');
  for (const l of affectedLayers) {
    console.log(`    Layer ${l.layer_id} — ${l.name}`);
  }

  console.log('\n' + '═'.repeat(70) + '\n');
}

main().catch(e => { console.error(e); process.exit(1); });
