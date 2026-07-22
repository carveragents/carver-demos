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

// The applicant ID carries the applicant's 2-letter state code, so a presenter only has to
// remember to swap "CO" -> "CA" -> "NY" while the number stays the same. The state still comes
// from the looked-up file (below), not from parsing the ID.
const APPLICANTS: Record<string, ApplicantProfile> = {
  'CO-1001': {
    applicantId: 'CO-1001',
    name: 'Marcus Webb',
    state: 'Colorado',
    application: { id: 'LN-4471', ...baseApplication },
  },
  'CA-1001': {
    applicantId: 'CA-1001',
    name: 'Dolores Ramirez',
    state: 'California',
    application: { id: 'LN-5182', ...baseApplication },
  },
  'NY-1001': {
    applicantId: 'NY-1001',
    name: 'Priya Nadella',
    state: 'New York',
    application: { id: 'LN-6093', ...baseApplication },
  },
};

/** Normalise "co-1001", " CO-1001 ", "CO1001" to the canonical key. */
const normalise = (raw: string): string => {
  const t = (raw ?? '').trim().toUpperCase().replace(/\s+/g, '');
  if (APPLICANTS[t]) return t;
  const m = t.match(/^([A-Z]{2})-?(\d+)$/);
  if (m) {
    const key = `${m[1]}-${m[2]}`;
    if (APPLICANTS[key]) return key;
  }
  return t;
};

export const lookupApplicant = createTool({
  id: 'lookup-applicant',
  description:
    "Look up a signed-in applicant's file by their applicant ID. Returns who they are, the state " +
    'they are in, and their loan application and its decision. Call this before answering questions ' +
    "about an applicant's application — do not ask the applicant for details their file already holds.",
  inputSchema: z.object({
    applicantId: z.string().min(1).describe('The applicant ID the person gave, e.g. "CO-1001"'),
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
        message: `No applicant found for ID "${inputData.applicantId}". Known demo IDs: CO-1001, CA-1001, NY-1001.`,
      };
    }
    return { found: true, profile, message: `Loaded file for ${profile.name} (${profile.state}).` };
  },
});
