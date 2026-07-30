import { LibSQLStore } from '@mastra/libsql';

/**
 * One store, shared by the Mastra instance (traces) and by demo memory (threads).
 *
 * Extracted from index.ts so both can use the SAME instance rather than two LibSQLStore objects
 * pointed at the same file, which would contend on the SQLite lock.
 */
export const demoStore = new LibSQLStore({
  id: 'mastra-storage',
  url: 'file:./mastra.db',
});
