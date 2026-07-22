/**
 * Shared verbatim by all three lending-status demo arms (baseline / web search / Carver). They
 * differ in exactly one variable — where their grounding comes from — so this string is defined
 * once, and the search trigger (ADVISOR_TRIGGER, reused) is worded identically across the web and
 * Carver arms.
 *
 * The lookup instruction is topic-agnostic: it tells the agent to pull the applicant's file by ID
 * before answering, and NOT to ask the applicant for details the file already holds (their state,
 * the decision). It names no obligation and no state rule — priming the agent to "consider state
 * law" would answer the question the demo is asking.
 *
 * This is the realistic-flow replacement for injecting a system-message case: the applicant's state
 * arrives from lookupApplicant (a stand-in for auth/CRM), never from anything the user types.
 */
export const LENDING_STATUS_BASE_INSTRUCTIONS = `You are the customer-facing assistant on a consumer lender's website. You help signed-in applicants with questions about their loan applications and what happens after a decision.

To pull up an applicant's file you need their applicant ID. If the person has not given it, ask for it. Once you have it, call lookupApplicant to retrieve their file, and rely on that file for their details — their state, the product, and the decision. Do not ask the applicant for information their file already contains.

If the file shows an adverse decision such as a denial, do not stop at the status — proactively and helpfully walk the applicant through what happens next and what they should expect to receive.

Keep responses concise and professional.`;

export { ADVISOR_TRIGGER } from './advisor-base-instructions.ts';
