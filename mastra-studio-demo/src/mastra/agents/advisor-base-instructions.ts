/**
 * Shared verbatim by every arm of the cross-domain silent-trigger mini-suite (crypto,
 * medical devices, online child-safety). The arms must differ in exactly one variable —
 * where their grounding comes from — so this string is defined once.
 *
 * Deliberately says nothing about regulation, compliance, licensing, or checking rules. The
 * whole hypothesis under test is whether an agent *notices* that an attribute of the company
 * or its situation triggers an obligation nobody named. Priming any arm to "consider
 * applicable law" would answer the question in the prompt and measure nothing.
 *
 * It also says nothing about which company, sector, or jurisdiction. That context — and the
 * naive question — is injected at runtime as a system message (see scripts/trigger-probe.mjs),
 * so one set of arms serves every scenario and the arms stay identical across domains.
 */
export const ADVISOR_BASE_INSTRUCTIONS = `You are an AI assistant deployed by a company to help its team with operational, product, and planning questions. The company you work for, the person you are speaking with, and today's date are described in the system message for this conversation.

Keep responses concise and professional.`;

/**
 * The trigger clause. Worded IDENTICALLY in the web-search arm and every Carver arm — same
 * trigger conditions, same obligations named (none), only the retrieval tool differs. If this
 * drifts between arms, any gap we measure could be prompt phrasing rather than data. Change it
 * in one place or not at all.
 */
export const ADVISOR_TRIGGER = `Before you tell someone what they or the company may do, must do, must not do, or are entitled to, search first and let what you find govern your answer. If you cannot find something, say so plainly rather than answering from memory.`;
