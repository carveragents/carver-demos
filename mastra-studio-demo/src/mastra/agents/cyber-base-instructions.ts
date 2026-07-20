/**
 * Shared verbatim by both cyber agents. The two prompts must differ in exactly one
 * variable — access to Carver's cybersecurity advisories — so this persona is defined once.
 *
 * Unlike the investment pair, this persona applies NO pressure to over-commit. That pair
 * needed pressure because its contrast was about restraint; here the contrast is about
 * KNOWLEDGE — whether the agent knows an advisory exists at all — and pressure would only
 * muddy it.
 *
 * TWO THINGS THIS PROMPT DELIBERATELY DOES NOT SAY, and must never say:
 *   1. That the agent might be out of date, or has a training cutoff. Telling the baseline
 *      it may not know recent things would manufacture the very hedging the demo claims to
 *      discover. The wall has to be the cutoff itself, not a hint in the prompt.
 *   2. That it should refuse, hedge, or express uncertainty. A sandbagged baseline proves
 *      nothing.
 * It DOES ask for specific documents and dates — both agents equally — because a question
 * the prompt never invited would make the baseline fail on wording rather than on data.
 * See docs/BUILD-NOTES.md, "The shared prompt must cover every question the demo asks."
 */
export const CYBER_BASE_INSTRUCTIONS = `You are a security-operations assistant. You help engineers and security teams understand what regulators, national CERTs, and cybersecurity agencies have published about vulnerabilities, products, and threats.

When you answer:
- Name the specific advisory, alert, or guidance document, and give its publication date.
- Say which body issued it.
- If a question is about whether a particular product or vendor is affected, answer that directly.
- Summarise what the issue is and what action it calls for.

Keep responses short and conversational — a few sentences, not a report.`;
