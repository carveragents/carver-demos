import assert from 'node:assert/strict';
import { test } from 'node:test';
import { type DomainRecord, runDomainQuery } from './carver-domain-query.ts';

// Hermetic fixtures. A real domain table holds ~2k records rebuilt from a moving feed
// snapshot, so tests that read it would fail for reasons unrelated to the filter/sort logic.

const record = (title: string, date: string, extra: Partial<DomainRecord> = {}): DomainRecord => ({
  title,
  date,
  updateType: 'advisory',
  regulator: 'Test Regulator',
  whatChanged: '',
  whyItMatters: '',
  keyRequirements: [],
  impactScore: 5,
  tags: [],
  sourceUrl: 'https://example.test/doc',
  ...extra,
});

const RECORDS: DomainRecord[] = [
  record('ANSSI supply chain advisory', '2026-04-01', {
    updateType: 'advisory',
    regulator: 'ANSSI',
    whatChanged: 'Mandatory vendor risk assessments for critical suppliers.',
    whyItMatters: 'Raises the compliance bar for critical infrastructure operators.',
    impactScore: 3,
    tags: ['SupplyChain'],
  }),
  record('CISA cloud guidance update', '2026-04-15', {
    updateType: 'guidance',
    regulator: 'CISA',
    whatChanged: 'Clarifies the shared responsibility model for agency cloud tenants.',
    whyItMatters: 'Helps agencies scope their cloud security obligations.',
    impactScore: null,
    tags: ['Cloud'],
  }),
  record('NCSC ransomware advisory', '2026-05-01', {
    updateType: 'advisory',
    regulator: 'NCSC',
    whatChanged: 'New reporting timelines for confirmed incidents.',
    whyItMatters: 'Speeds incident response coordination across sectors.',
    impactScore: 8,
    tags: ['IncidentResponse'],
  }),
  record('ANSSI cryptography guidance', '2026-05-10', {
    updateType: 'guidance',
    regulator: 'ANSSI',
    whatChanged: 'Updated the approved algorithm list for regulated entities.',
    whyItMatters: 'Affects procurement of cryptographic modules.',
    impactScore: 6,
    tags: ['Cryptography'],
  }),
  record('CISA critical vulnerability advisory', '2026-05-20', {
    updateType: 'advisory',
    regulator: 'CISA',
    whatChanged: 'Patch required within 48 hours for internet-facing systems.',
    whyItMatters: 'High exploitation risk for federal systems.',
    impactScore: 9,
    tags: ['Vulnerability'],
  }),
  record('NCSC cloud security guidance', '2026-06-01', {
    updateType: 'guidance',
    regulator: 'NCSC',
    whatChanged: 'Baseline controls for cloud migration in the public sector.',
    whyItMatters: 'Sets a minimum bar for public sector cloud adoption.',
    impactScore: null,
    tags: ['Cloud', 'PublicSector'],
  }),
  record('ANSSI phishing campaign advisory', '2026-06-05', {
    updateType: 'advisory',
    regulator: 'ANSSI',
    whatChanged: 'Details a targeted phishing campaign against the finance sector.',
    whyItMatters: 'Warns finance sector firms of an active threat.',
    impactScore: 2,
    tags: ['Phishing'],
  }),
  record('CISA zero trust guidance', '2026-06-15', {
    updateType: 'guidance',
    regulator: 'CISA',
    whatChanged: 'Reference architecture for zero trust adoption.',
    whyItMatters: 'Aligns agencies to the federal zero trust mandate.',
    impactScore: 9,
    tags: ['ZeroTrust'],
  }),
];

test('dateFrom is inclusive of the boundary date', () => {
  const result = runDomainQuery(RECORDS, { dateFrom: '2026-05-01' });

  assert.equal(result.matchCount, 6);
  assert.ok(result.records.every((r) => r.date >= '2026-05-01'));
});

test('dateTo is inclusive of the boundary date', () => {
  const result = runDomainQuery(RECORDS, { dateTo: '2026-05-20' });

  assert.equal(result.matchCount, 5);
  assert.ok(result.records.every((r) => r.date <= '2026-05-20'));
});

test('dateFrom and dateTo together bound the range on both sides', () => {
  const result = runDomainQuery(RECORDS, { dateFrom: '2026-05-01', dateTo: '2026-05-20' });

  assert.equal(result.matchCount, 3);
  assert.deepEqual(
    result.records.map((r) => r.date),
    ['2026-05-20', '2026-05-10', '2026-05-01'],
  );
});

test('minImpact filters out records below the threshold', () => {
  const result = runDomainQuery(RECORDS, { minImpact: 6 });

  assert.equal(result.matchCount, 4);
  assert.ok(result.records.every((r) => (r.impactScore ?? -1) >= 6));
});

test('minImpact excludes records with a null score even at a low threshold', () => {
  const result = runDomainQuery(RECORDS, { minImpact: 0 });

  // 6 of the 8 fixture records have a non-null score; the other 2 are null and must
  // be excluded even though a threshold of 0 would pass any real score.
  assert.equal(result.matchCount, 6);
  assert.ok(result.records.every((r) => r.impactScore !== null));
});

test('updateType matches case-insensitively', () => {
  const result = runDomainQuery(RECORDS, { updateType: 'ADVISORY' });

  assert.equal(result.matchCount, 4);
  assert.ok(result.records.every((r) => r.updateType === 'advisory'));
});

test('updateType is an exact match, not a substring', () => {
  const result = runDomainQuery(RECORDS, { updateType: 'advis' });

  assert.equal(result.matchCount, 0);
});

test('regulator matches case-insensitively as a substring', () => {
  const result = runDomainQuery(RECORDS, { regulator: 'ans' });

  assert.equal(result.matchCount, 3);
  assert.ok(result.records.every((r) => r.regulator === 'ANSSI'));

  const upper = runDomainQuery(RECORDS, { regulator: 'cisa' });
  assert.equal(upper.matchCount, 3);
});

test('keyword searches the title', () => {
  const result = runDomainQuery(RECORDS, { keyword: 'ransomware' });

  assert.equal(result.matchCount, 1);
  assert.equal(result.records[0].title, 'NCSC ransomware advisory');
});

test('keyword searches whatChanged', () => {
  const result = runDomainQuery(RECORDS, { keyword: '48 hours' });

  assert.equal(result.matchCount, 1);
  assert.equal(result.records[0].title, 'CISA critical vulnerability advisory');
});

test('keyword searches whyItMatters', () => {
  const result = runDomainQuery(RECORDS, { keyword: 'federal zero trust mandate' });

  assert.equal(result.matchCount, 1);
  assert.equal(result.records[0].title, 'CISA zero trust guidance');
});

test('keyword searches tags', () => {
  const result = runDomainQuery(RECORDS, { keyword: 'supplychain' });

  assert.equal(result.matchCount, 1);
  assert.equal(result.records[0].title, 'ANSSI supply chain advisory');
});

test('filters combine with AND, not OR', () => {
  const result = runDomainQuery(RECORDS, { regulator: 'ANSSI', updateType: 'guidance' });

  assert.equal(result.matchCount, 1);
  assert.equal(result.records[0].title, 'ANSSI cryptography guidance');
});

test('default ordering is date descending', () => {
  const result = runDomainQuery(RECORDS, {});

  assert.deepEqual(
    result.records.map((r) => r.date),
    ['2026-06-15', '2026-06-05', '2026-06-01', '2026-05-20', '2026-05-10', '2026-05-01', '2026-04-15', '2026-04-01'],
  );
});

test('orderBy impactScore ranks highest first', () => {
  const result = runDomainQuery(RECORDS, { orderBy: 'impactScore' });

  assert.deepEqual(
    result.records.slice(0, 6).map((r) => r.impactScore),
    [9, 9, 8, 6, 3, 2],
  );
});

test('orderBy impactScore sorts null-score records last', () => {
  const result = runDomainQuery(RECORDS, { orderBy: 'impactScore' });

  assert.deepEqual(result.records.slice(-2).map((r) => r.impactScore), [null, null]);
});

test('orderBy impactScore breaks ties by date descending', () => {
  const result = runDomainQuery(RECORDS, { regulator: 'CISA', orderBy: 'impactScore' });

  // record5 (2026-05-20) and record8 (2026-06-15) both score 9; the later date wins.
  assert.equal(result.records[0].title, 'CISA zero trust guidance');
  assert.equal(result.records[1].title, 'CISA critical vulnerability advisory');
});

test('limit truncates records but matchCount still reports the true total', () => {
  const result = runDomainQuery(RECORDS, { limit: 3 });

  assert.equal(result.matchCount, 8);
  assert.equal(result.records.length, 3);
  assert.equal(result.records[0].date, '2026-06-15');
});

test('limit is clamped to a minimum of 1', () => {
  const result = runDomainQuery(RECORDS, { limit: 0 });

  assert.equal(result.matchCount, 8);
  assert.equal(result.records.length, 1);
});

test('limit is clamped to a maximum of 100 (MAX_LIMIT)', () => {
  const bulk = Array.from({ length: 150 }, (_, i) => record(`Bulk record ${i}`, '2026-01-01'));

  const result = runDomainQuery(bulk, { limit: 500 });

  assert.equal(result.matchCount, 150);
  assert.equal(result.records.length, 100);
});

test('groupBy regulator returns counts and leaves records empty', () => {
  const result = runDomainQuery(RECORDS, { groupBy: 'regulator' });

  assert.equal(result.matchCount, 8);
  assert.deepEqual(result.records, []);
  assert.equal(result.groups.length, 3);
  assert.equal(result.groups.find((g) => g.key === 'ANSSI')?.count, 3);
  assert.equal(result.groups.find((g) => g.key === 'CISA')?.count, 3);
  assert.equal(result.groups.find((g) => g.key === 'NCSC')?.count, 2);
});

test('groupBy month buckets by YYYY-MM', () => {
  const result = runDomainQuery(RECORDS, { groupBy: 'month' });

  assert.equal(result.groups.length, 3);
  assert.equal(result.groups.find((g) => g.key === '2026-04')?.count, 2);
  assert.equal(result.groups.find((g) => g.key === '2026-05')?.count, 3);
  assert.equal(result.groups.find((g) => g.key === '2026-06')?.count, 3);
});

test('groupBy updateType groups by update type', () => {
  const result = runDomainQuery(RECORDS, { groupBy: 'updateType' });

  assert.equal(result.groups.length, 2);
  assert.equal(result.groups.find((g) => g.key === 'advisory')?.count, 4);
  assert.equal(result.groups.find((g) => g.key === 'guidance')?.count, 4);
});

test('groups are sorted by count descending, ties broken by key ascending', () => {
  const result = runDomainQuery(RECORDS, { groupBy: 'regulator' });

  // ANSSI and CISA tie at 3; alphabetical order breaks the tie ahead of NCSC's 2.
  assert.deepEqual(
    result.groups.map((g) => g.key),
    ['ANSSI', 'CISA', 'NCSC'],
  );
});

test('group maxImpact reports the highest score in the group', () => {
  const result = runDomainQuery(RECORDS, { groupBy: 'regulator' });

  assert.equal(result.groups.find((g) => g.key === 'ANSSI')?.maxImpact, 6);
  assert.equal(result.groups.find((g) => g.key === 'CISA')?.maxImpact, 9);
  assert.equal(result.groups.find((g) => g.key === 'NCSC')?.maxImpact, 8);
});

test('group maxImpact is null when every member in the group has a null score', () => {
  const result = runDomainQuery(RECORDS, { keyword: 'cloud', groupBy: 'regulator' });

  assert.equal(result.matchCount, 2);
  assert.equal(result.groups.find((g) => g.key === 'CISA')?.maxImpact, null);
  assert.equal(result.groups.find((g) => g.key === 'NCSC')?.maxImpact, null);
});

test('an empty record list returns zero rather than throwing', () => {
  const result = runDomainQuery([], {});

  assert.equal(result.matchCount, 0);
  assert.deepEqual(result.records, []);
  assert.deepEqual(result.groups, []);
});

test('a query with no filters returns everything up to the default limit', () => {
  const result = runDomainQuery(RECORDS, {});

  assert.equal(result.matchCount, 8);
  assert.equal(result.records.length, 8);
});
