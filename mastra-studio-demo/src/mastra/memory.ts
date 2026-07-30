import { Memory } from '@mastra/memory';
import { demoStore } from './storage.ts';

/**
 * Shared memory for the three lending-status arms.
 *
 * WHY: Studio only persists a conversation as a re-openable thread when the agent has memory
 * configured — without it, the chat URL gets a thread id during the run but reloads empty
 * ("Memory not enabled"). The demo video records real saved conversations, so the threads have to
 * survive a reload.
 *
 * WHY SHARED: the three arms are a controlled comparison — same model, same base instructions, same
 * trigger clause, retrieval the only variable. Memory is configuration, not prompt, but it still has
 * to be IDENTICAL across arms or the comparison is no longer clean. One exported instance makes that
 * structural instead of a thing three files have to agree about.
 *
 * Defaults only: conversation history, no working memory, no semantic recall. The demo is one
 * message per thread, so there is no prior history to inject and the measured behaviour should not
 * move. That is an assumption to VERIFY, not assert — re-run scripts/lending-status-probe.mjs after
 * any change here and confirm the content grid and token medians hold.
 */
export const demoMemory = new Memory({
  storage: demoStore,
});
