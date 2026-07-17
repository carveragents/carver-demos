/**
 * Builds data/carver-updates.json — the vendored fixture of recent regulatory updates.
 *
 * Streams carver-showcase's annotations.jsonl (1.7 GB, 244k records; build time only) and
 * keeps a recent-first slice for the topics already in data/carver-topics.json.
 * Deterministic: same inputs -> byte-identical output.
 *
 * Selection is neutral — most recent per topic. Records are NOT selected by matching the
 * demo questions; a fixture rigged to a script collapses on the first adjacent question.
 *
 * Spec: docs/superpowers/specs/2026-07-16-carver-updates-tool-design.md
 * Usage: node scripts/build-updates.mjs
 */
import { createReadStream, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, parse as parsePath } from 'node:path';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { MARQUEE } from './marquee.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = join(HERE, '..');

/** See build-topics.mjs — worktree and main checkout sit at different depths. */
function findUpward(start, relative) {
  let dir = start;
  for (;;) {
    const candidate = join(dir, relative);
    if (existsSync(candidate)) return candidate;
    const parent = dirname(dir);
    if (parent === dir || dir === parsePath(dir).root) {
      throw new Error(
        `could not find "${relative}" in any ancestor of ${start}.\n` +
          `This build script needs the sibling carver-showcase repo checked out.\n` +
          `The vendored data/carver-updates.json is committed, so the demo runs without it —\n` +
          `you only need carver-showcase to regenerate the fixture.`,
      );
    }
    dir = parent;
  }
}

const TOPICS = join(PROJECT, 'data/carver-topics.json');
const ANNOTATIONS = findUpward(PROJECT, 'carver-showcase/data/annotations.jsonl');
const SNAPSHOT_META = findUpward(PROJECT, 'carver-showcase/data/snapshot_meta.json');
const OUT = join(PROJECT, 'data/carver-updates.json');

const PER_MARQUEE = 30;
const PER_OTHER = 3;
const MAX_KEY_REQUIREMENTS = 3;
const MAX_TAGS = 8;

const topics = JSON.parse(readFileSync(TOPICS, 'utf8'));
const byTopicId = new Map(topics.map((t) => [t.topicId, t]));
const marqueeNames = new Set(MARQUEE);
const marqueeIds = new Set(topics.filter((t) => marqueeNames.has(t.name)).map((t) => t.topicId));

// Records dated after the snapshot are forward-dated junk (the source range runs to 2569).
// Anchoring to the snapshot rather than today's date keeps rebuilds reproducible.
const snapshotDate = JSON.parse(readFileSync(SNAPSHOT_META, 'utf8')).snapshot_date;

const isUsableDate = (date) =>
  typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date) && date >= '2000-01-01' && date <= snapshotDate;

const trim = (record) => {
  const out = record.output_data ?? {};
  const cls = out.classification ?? {};
  const meta = out.metadata ?? {};
  const summary = meta.impact_summary ?? {};
  const scores = out.scores ?? {};

  return {
    topicId: record.topic_id,
    title: cls.metadata?.title ?? '',
    date: out.reconciled_published_date?.date ?? '',
    updateType: cls.update_type ?? '',
    regulator: cls.regulatory_source?.name ?? '',
    country: cls.jurisdiction?.country ?? '',
    impact: scores.impact?.label ?? '',
    impactScore: scores.impact?.score ?? null,
    urgency: scores.urgency?.label ?? '',
    whatChanged: summary.what_changed ?? '',
    whyItMatters: summary.why_it_matters ?? '',
    keyRequirements: (summary.key_requirements ?? []).slice(0, MAX_KEY_REQUIREMENTS),
    tags: (meta.tags ?? []).slice(0, MAX_TAGS),
  };
};

const collected = new Map(); // topicId -> trimmed records
let scanned = 0;
let skippedDate = 0;

const lines = createInterface({ input: createReadStream(ANNOTATIONS), crlfDelay: Infinity });

for await (const line of lines) {
  scanned += 1;
  if (!line) continue;

  let record;
  try {
    record = JSON.parse(line);
  } catch {
    continue;
  }

  const topicId = record.topic_id;
  if (!byTopicId.has(topicId)) continue;

  const update = trim(record);
  if (!isUsableDate(update.date) || !update.title) {
    skippedDate += 1;
    continue;
  }

  if (!collected.has(topicId)) collected.set(topicId, []);
  collected.get(topicId).push(update);
}

// Sort by date desc, then title, so ties resolve identically on every rebuild.
const byDateDesc = (a, b) => (a.date === b.date ? a.title.localeCompare(b.title) : b.date.localeCompare(a.date));

const selected = [];
for (const [topicId, records] of collected) {
  const cap = marqueeIds.has(topicId) ? PER_MARQUEE : PER_OTHER;
  records.sort(byDateDesc);
  selected.push(...records.slice(0, cap));
}

// Stable output order: newest first overall, ties broken by topicId then title.
selected.sort((a, b) =>
  a.date === b.date
    ? a.topicId === b.topicId
      ? a.title.localeCompare(b.title)
      : a.topicId.localeCompare(b.topicId)
    : b.date.localeCompare(a.date),
);

writeFileSync(OUT, `${JSON.stringify(selected, null, 2)}\n`);

const missingMarquee = MARQUEE.filter((name) => {
  const topic = topics.find((t) => t.name === name);
  return !topic || !collected.has(topic.topicId);
});
const emptyTopics = topics.filter((t) => !collected.has(t.topicId));
const bytes = Buffer.byteLength(readFileSync(OUT));

console.log(`scanned:          ${scanned.toLocaleString()} annotation records`);
console.log(`skipped (date/title): ${skippedDate.toLocaleString()}`);
console.log(`topics with updates:  ${collected.size} of ${topics.length}`);
console.log(`selected:         ${selected.length} records  (${(bytes / 1024).toFixed(0)} KB)`);
console.log(`date range:       ${selected.at(-1)?.date} … ${selected[0]?.date}  (snapshot ${snapshotDate})`);
if (emptyTopics.length) {
  console.log(`no updates (${emptyTopics.length}): ${emptyTopics.map((t) => t.acronym || t.name).join(', ')}`);
}
if (missingMarquee.length) {
  console.log(`WARNING marquee bodies with no updates: ${missingMarquee.join(', ')}`);
}
console.log(`wrote ${OUT}`);
