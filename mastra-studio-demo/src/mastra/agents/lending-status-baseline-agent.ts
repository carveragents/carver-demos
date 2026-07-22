import { Agent } from '@mastra/core/agent';
import { LENDING_STATUS_BASE_INSTRUCTIONS } from './lending-status-instructions.ts';
import { lookupApplicant } from '../tools/lookup-applicant-tool.ts';

/**
 * The control for the lending-status demo: it can look up the applicant's file (auth/CRM stand-in),
 * but has no regulatory grounding — it answers obligation questions from model memory alone.
 * lookupApplicant is a function tool only (no provider-defined tool), so nothing is dropped.
 */
export const lendingStatusBaselineAgent = new Agent({
  id: 'lending-status-baseline-agent',
  name: 'Lending Status — Baseline (no data)',
  instructions: LENDING_STATUS_BASE_INSTRUCTIONS,
  model: 'openai/gpt-5.6-sol',
  tools: { lookupApplicant },
});
