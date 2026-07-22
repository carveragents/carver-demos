/**
 * lookupApplicant — the stand-in for auth / CRM lookup in the lending-status demo.
 *
 * In production, a signed-in applicant's context (who they are, where they are, their
 * application and its decision) is injected by auth middleware — the user never types it.
 * The demo simulates that: the agent asks for an applicant ID, calls this tool, and gets the
 * profile back. The tool RESULT is visible in the Studio trace, so the audience can see the
 * applicant's STATE came from the lookup, not from anything the user said.
 *
 * The three profiles are identical except for the state — same declined home-improvement loan,
 * same automated-model denial — so the applicant's state is the one variable in the demo.
 */
import { createTool } from '@mastra/core/tools';
import { z } from 'zod';

/** One applicant's file, as returned to the agent. Same shape for every applicant. */
export type ApplicantProfile = {
  applicantId: string;
  name: string;
  state: string;
  application: {
    id: string;
    product: string;
    collateral: string;
    status: string;
    decisionMethod: string;
    modelScore: number;
    approvalCutoff: number;
    fileComplete: boolean;
    decisionDate: string;
  };
};

/** Same loan and same denial for everyone — only `state` differs. */
const baseApplication = {
  product: 'Home improvement loan',
  collateral: "Owner-occupied one-to-four-unit residence",
  status: 'Declined',
  decisionMethod: 'Automated underwriting model',
  modelScore: 611,
  approvalCutoff: 640,
  fileComplete: true,
  decisionDate: '2027-01-14',
};

const APPLICANTS: Record<string, ApplicantProfile> = {
  'A-1001': {
    applicantId: 'A-1001',
    name: 'Marcus Webb',
    state: 'Colorado',
    application: { id: 'LN-4471', ...baseApplication },
  },
  'A-1002': {
    applicantId: 'A-1002',
    name: 'Dolores Ramirez',
    state: 'California',
    application: { id: 'LN-5182', ...baseApplication },
  },
  'A-1003': {
    applicantId: 'A-1003',
    name: 'Priya Nadella',
    state: 'New York',
    application: { id: 'LN-6093', ...baseApplication },
  },
};

/** Normalise "a-1001", " A-1001 ", "1001" to the canonical key. */
const normalise = (raw: string): string => {
  const t = (raw ?? '').trim().toUpperCase();
  if (APPLICANTS[t]) return t;
  const withPrefix = `A-${t.replace(/^A-?/, '')}`;
  return APPLICANTS[withPrefix] ? withPrefix : t;
};

export const lookupApplicant = createTool({
  id: 'lookup-applicant',
  description:
    "Look up a signed-in applicant's file by their applicant ID. Returns who they are, the state " +
    'they are in, and their loan application and its decision. Call this before answering questions ' +
    "about an applicant's application — do not ask the applicant for details their file already holds.",
  inputSchema: z.object({
    applicantId: z.string().min(1).describe('The applicant ID the person gave, e.g. "A-1001"'),
  }),
  outputSchema: z.object({
    found: z.boolean(),
    profile: z
      .object({
        applicantId: z.string(),
        name: z.string(),
        state: z.string().describe('The applicant\'s state — governs which obligations apply'),
        application: z.object({
          id: z.string(),
          product: z.string(),
          collateral: z.string(),
          status: z.string(),
          decisionMethod: z.string(),
          modelScore: z.number(),
          approvalCutoff: z.number(),
          fileComplete: z.boolean(),
          decisionDate: z.string(),
        }),
      })
      .nullable(),
    message: z.string(),
  }),
  execute: async (inputData) => {
    const key = normalise(inputData.applicantId);
    const profile = APPLICANTS[key];
    if (!profile) {
      return {
        found: false,
        profile: null,
        message: `No applicant found for ID "${inputData.applicantId}". Known demo IDs: A-1001, A-1002, A-1003.`,
      };
    }
    return { found: true, profile, message: `Loaded file for ${profile.name} (${profile.state}).` };
  },
});
