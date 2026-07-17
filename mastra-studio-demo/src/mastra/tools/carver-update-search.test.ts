import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { TopicRecord } from './carver-topic-search.ts';
import { type UpdateRecord, searchUpdates } from './carver-update-search.ts';

// Hermetic fixtures. The real fixture is rebuilt from a moving 1.7 GB snapshot, so tests
// that read it would fail for reasons unrelated to the matcher.

const topic = (topicId: string, name: string, acronym: string, jurisdiction: string): TopicRecord => ({
  topicId,
  name,
  acronym,
  jurisdiction,
  system: 'GICS',
  sector: 'Financials',
  industry: 'Capital Markets',
  subIndustry: 'Investment Banking & Brokerage',
  confidence: 'high',
});

const update = (topicId: string, date: string, title: string, extra: Partial<UpdateRecord> = {}): UpdateRecord => ({
  topicId,
  title,
  date,
  updateType: 'bulletin',
  regulator: 'Test Regulator',
  country: 'US',
  impact: 'medium',
  impactScore: 5,
  urgency: 'low',
  whatChanged: '',
  whyItMatters: '',
  keyRequirements: [],
  tags: [],
  ...extra,
});

const TOPICS: TopicRecord[] = [
  topic('t-fca', 'Financial Conduct Authority', 'FCA', 'GB'),
  topic('t-sec-us', 'U.S. Securities and Exchange Commission', 'SEC', 'US'),
  topic('t-sec-gh', 'Securities and Exchange Commission Ghana', 'SEC', 'GH'),
  topic('t-quiet', 'Quiet Regulator With No Updates', 'QRNU', 'MT'),
];

const UPDATES: UpdateRecord[] = [
  update('t-fca', '2026-06-15', 'FCA crypto asset consultation'),
  update('t-fca', '2026-01-05', 'FCA annual report', { tags: ['Governance', 'Reporting'] }),
  update('t-fca', '2026-03-20', 'FCA mortgage rules', { whatChanged: 'Revised affordability stress testing.' }),
  update('t-sec-us', '2026-05-01', 'SEC disclosure rule'),
  update('t-sec-gh', '2026-04-02', 'SEC Ghana licensing notice'),
];

test('returns a regulator’s updates newest first', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: 'FCA' });

  assert.equal(result.matchCount, 3);
  assert.deepEqual(
    result.updates.map((u) => u.date),
    ['2026-06-15', '2026-03-20', '2026-01-05'],
  );
});

test('keyword filters over the title', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: 'FCA', keyword: 'crypto' });

  assert.equal(result.matchCount, 1);
  assert.equal(result.updates[0].title, 'FCA crypto asset consultation');
});

test('keyword filters over tags', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: 'FCA', keyword: 'governance' });

  assert.equal(result.matchCount, 1);
  assert.equal(result.updates[0].title, 'FCA annual report');
});

test('keyword filters over whatChanged', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: 'FCA', keyword: 'affordability' });

  assert.equal(result.matchCount, 1);
  assert.equal(result.updates[0].title, 'FCA mortgage rules');
});

test('keyword matching is case-insensitive', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: 'FCA', keyword: 'CRYPTO' });

  assert.equal(result.matchCount, 1);
});

test('an ambiguous acronym reports every jurisdiction rather than picking one', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: 'SEC' });

  assert.equal(result.matchCount, 2);
  assert.deepEqual(
    result.ambiguousRegulators.map((r) => r.jurisdiction).sort(),
    ['GH', 'US'],
  );
});

test('an unambiguous regulator reports no ambiguity', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: 'FCA' });

  assert.deepEqual(result.ambiguousRegulators, []);
});

test('a known regulator with no updates returns zero, not an error', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: 'QRNU' });

  assert.equal(result.matchCount, 0);
  assert.deepEqual(result.updates, []);
});

test('an unknown regulator returns zero instead of guessing', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: 'Reykjavik Bicycle Authority' });

  assert.equal(result.matchCount, 0);
  assert.deepEqual(result.updates, []);
});

test('limit truncates updates but matchCount still reports the true total', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: 'FCA', limit: 2 });

  assert.equal(result.matchCount, 3);
  assert.equal(result.updates.length, 2);
  assert.equal(result.updates[0].date, '2026-06-15');
});

test('an empty regulator returns zero', () => {
  const result = searchUpdates(TOPICS, UPDATES, { regulator: '   ' });

  assert.equal(result.matchCount, 0);
});
