import { Agent } from '@mastra/core/agent';
import { LENDING_STATUS_BASE_INSTRUCTIONS } from './lending-status-instructions.ts';
import { lookupApplicant } from '../tools/lookup-applicant-tool.ts';
import { demoMemory } from '../memory.ts';

/**
 * The control for the lending-status demo: it can look up the applicant's file (auth/CRM stand-in),
 * but has no regulatory grounding — it answers obligation questions from model memory alone.
 * lookupApplicant is a function tool only (no provider-defined tool), so nothing is dropped.
 */
export const lendingStatusBaselineAgent = new Agent({
  id: 'lending-status-baseline-agent',
  name: 'Lending Status — Baseline (no data)',
  // `description` is API-only metadata: verified 2026-07-28 that Mastra Studio v1.51.0 renders the
  // raw INSTRUCTIONS in the agent list and never surfaces `description` anywhere in the UI. Kept
  // regardless — it is what any API consumer (or the Mastra team) sees when inspecting /api/agents,
  // and it names the one axis these three arms differ on.
  //
  // Design-partner note for Mastra: when several agents intentionally share a prompt — the normal
  // shape of a controlled comparison — the list's instructions column renders three identical rows
  // and `description` would be the more useful thing to show.
  description: 'Control arm. Can look up the applicant file, but has no regulatory data — it answers obligation questions from model memory alone.',
  instructions: LENDING_STATUS_BASE_INSTRUCTIONS,
  model: 'openai/gpt-5.6-sol',
  // Same step cap on all three arms. The probe always passed maxSteps: 8 explicitly, so this never
  // affected a measurement — but the arms differed in source, and the demo video puts the arm diff
  // on screen. Retrieval must be the ONLY difference a viewer can find.
  defaultOptions: { maxSteps: 8 },
  tools: { lookupApplicant },
  memory: demoMemory,
});
