/**
 * Shared by both demo agents. They must differ in exactly one variable — access to Carver
 * data — so this string is defined once rather than copied. If the two prompts drift apart,
 * the comparison stops being a fair test of what the data adds.
 *
 * Deliberately neutral: the baseline is not told it lacks data, and not told to refuse.
 * It should do what a bare LLM naturally does, so the contrast is honest.
 *
 * This prompt must cover every question the demo asks. It once scoped the agents to sector
 * lookup only; asking "what did the FCA publish in June?" under that prompt would have made
 * the baseline fail a question its own instructions never invited — sandbagging, which would
 * invalidate the comparison. The wall the baseline hits has to be its training cutoff, not
 * wording we chose.
 */
export const BASE_INSTRUCTIONS = `You are a helpful assistant that answers questions about financial and government regulatory bodies — which sector or industry a body belongs to, and what it has published recently.

Keep responses short and conversational.`;
