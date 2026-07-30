import { Mastra } from '@mastra/core/mastra';
import { PinoLogger } from '@mastra/loggers';
import { demoStore } from './storage.ts';
import { MastraStorageExporter, Observability } from '@mastra/observability';
import { lendingStatusBaselineAgent } from './agents/lending-status-baseline-agent.ts';
import { lendingStatusWebsearchAgent } from './agents/lending-status-websearch-agent.ts';
import { lendingStatusCarverAgent } from './agents/lending-status-carver-agent.ts';

export const mastra = new Mastra({
  // Only the two demo-usable scenarios are registered. The other agents (investment, cyber,
  // lending, and the crypto/device/child-safety mini-suite) were measurement exercises that
  // ended in parity with web search — their write-ups live in docs/DEMO.md and their source
  // files remain in the repo, but they are intentionally NOT registered so Studio shows only
  // what actually demos. To bring one back, re-add its import and registry entry.
  agents: {
    // Scenario 1 (baselineAgent, carverAgent) was UNREGISTERED on 2026-07-28 for the demo video:
    // Studio shows only registered agents, and the video's whole point is that three arms differ by
    // exactly one thing. Two extra agents from an unrelated scenario invite "what are those?" at the
    // worst moment. Source retained in agents/{baseline,carver}-agent.ts — re-add the import and an
    // entry here to bring them back.
    //
    // Winning scenario — lending-status demo. The applicant asks for their loan status and gives an
    // applicant ID; the agent looks up their file (lookupApplicant, an auth/CRM stand-in) which
    // carries their STATE, then answers. Same denial for every applicant, state is the one variable:
    // the Carver arm surfaces the state obligation (CO AI Act, CA Holden Act) that baseline and web
    // miss. IDs CO-1001 (CO) / CA-1001 (CA) / NY-1001 (NY). See docs/DEMO.md.
    lendingStatusBaselineAgent,
    lendingStatusWebsearchAgent,
    lendingStatusCarverAgent,
  },
  // Storage + observability are what make Studio's Traces view work;
  // without them the exporter disables itself and traces are never persisted.
  // Same instance backs the lending-status arms' memory (see memory.ts), so Studio can re-open a
  // recorded conversation as a thread.
  storage: demoStore,
  logger: new PinoLogger({
    name: 'Mastra',
    level: 'info',
  }),
  observability: new Observability({
    configs: {
      default: {
        serviceName: 'mastra-studio-demo',
        exporters: [new MastraStorageExporter()],
      },
    },
  }),
});
