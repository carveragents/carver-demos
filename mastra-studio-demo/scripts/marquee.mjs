/**
 * Globally recognizable bodies, shared by both fixture builders.
 *
 * Lives in its own module so build-topics.mjs and build-updates.mjs cannot drift apart:
 * the topics fixture guarantees these are present, and the updates fixture gives these same
 * bodies their extra depth. Two copies of this list would eventually disagree, and the
 * failure would be silent — a marquee regulator with a classification but no updates.
 */
export const MARQUEE = [
  'U.S. Securities and Exchange Commission',
  'Financial Conduct Authority',
  'Federal Reserve System',
  'European Central Bank',
  'Bank of England',
  'Monetary Authority of Singapore',
  'Bank for International Settlements',
  'Commodity Futures Trading Commission',
  'Federal Deposit Insurance Corporation',
  'Consumer Financial Protection Bureau',
  'Federal Trade Commission',
  'European Banking Authority',
  'Australian Prudential Regulation Authority',
  'Australian Securities and Investments Commission',
  'Reserve Bank of Australia',
  'Environmental Protection Agency',
  "Information Commissioner's Office",
  '한국은행',
  '금융감독원',
  '금융위원회',
  '한국환경공단',
];
