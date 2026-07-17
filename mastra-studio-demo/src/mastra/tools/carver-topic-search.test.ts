import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadTopics, searchTopics } from './carver-topic-search.ts';

const topics = loadTopics();

test('an exact acronym outranks records that merely contain the word', () => {
  // "SEC" substring-matches 14 "Securities" records; none may displace the acronym hits.
  const result = searchTopics(topics, 'SEC');

  assert.ok(
    result.matches.every((m) => m.acronym.toUpperCase() === 'SEC'),
    'every match should be an exact acronym hit, not a "Securities" substring hit',
  );
});

test('a name prefix beats a mid-name mention', () => {
  // "Securities" starts 4 names but appears inside 14. The prefix tier wins outright.
  const result = searchTopics(topics, 'Securities');

  assert.equal(result.matchCount, 4);
  assert.ok(
    result.matches.every((m) => m.name.toLowerCase().startsWith('securities')),
    'a mid-name mention must not reach the answer while prefix matches exist',
  );
});

test('falls through to substring only when every better tier is empty', () => {
  // "exchange" starts no name and is no acronym, so the substring tier answers.
  const result = searchTopics(topics, 'exchange');

  assert.equal(result.matchCount, 4);
  assert.ok(result.matches.every((m) => /exchange/i.test(m.name)));
  assert.ok(result.matches.every((m) => !m.name.toLowerCase().startsWith('exchange')));
});

test('reports a miss instead of guessing', () => {
  const result = searchTopics(topics, 'zzzznotarealregulator');

  assert.deepEqual(result, { matchCount: 0, matches: [] });
});

test('limit truncates matches but matchCount still reports the true total', () => {
  const result = searchTopics(topics, 'SEC', 2);

  assert.equal(result.matches.length, 2);
  assert.equal(result.matchCount, 5, 'matchCount must not be truncated, or the agent cannot say "showing 2 of 5"');
});

test('matches a non-Latin name by acronym', () => {
  const result = searchTopics(topics, 'BOK');

  assert.equal(result.matchCount, 1);
  assert.equal(result.matches[0].name, '한국은행');
  assert.equal(result.matches[0].sector, 'Financials');
});

test('ignores case and surrounding whitespace', () => {
  assert.equal(searchTopics(topics, '  sec  ').matchCount, 5);
});

test('an empty query is a miss, not a match-everything', () => {
  assert.deepEqual(searchTopics(topics, '   '), { matchCount: 0, matches: [] });
});

test('finds a topic by its full name', () => {
  const result = searchTopics(topics, 'Financial Conduct Authority');

  assert.equal(result.matchCount, 1);
  assert.equal(result.matches[0].acronym, 'FCA');
  assert.equal(result.matches[0].jurisdiction, 'GB');
});

test('an ambiguous acronym returns every jurisdiction, not a guess', () => {
  const result = searchTopics(topics, 'SEC');

  assert.equal(result.matchCount, 5);
  const jurisdictions = result.matches.map((m) => m.jurisdiction).sort();
  assert.deepEqual(jurisdictions, ['GH', 'NG', 'TH', 'TH', 'US']);
  assert.ok(
    result.matches.some((m) => m.name === 'U.S. Securities and Exchange Commission'),
    'the US SEC must be among the matches',
  );
});

test('a query more specific than the stored name still finds the body', () => {
  // Agents pass through what the user said. "UK Financial Conduct Authority" is how people
  // refer to the FCA, but the record is named "Financial Conduct Authority" — so only
  // checking whether the name contains the query reports a false absence.
  const result = searchTopics(topics, 'UK Financial Conduct Authority');

  assert.equal(result.matchCount, 1);
  assert.equal(result.matches[0].acronym, 'FCA');
});

test('a specific query does not outrank an exact acronym match', () => {
  // Reverse containment is the last resort: it must never pre-empt a better tier.
  const result = searchTopics(topics, 'SEC');

  assert.equal(result.matchCount, 5);
});
