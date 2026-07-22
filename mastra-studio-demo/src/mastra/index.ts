import { Mastra } from '@mastra/core/mastra';
import { LibSQLStore } from '@mastra/libsql';
import { PinoLogger } from '@mastra/loggers';
import { MastraStorageExporter, Observability } from '@mastra/observability';
import { baselineAgent } from './agents/baseline-agent.ts';
import { carverAgent } from './agents/carver-agent.ts';
import { advisorBaselineAgent } from './agents/advisor-baseline-agent.ts';
import { advisorWebsearchAgent } from './agents/advisor-websearch-agent.ts';
import { stateLendingCarverAgent } from './agents/state-lending-carver-agent.ts';

export const mastra = new Mastra({
  // Only the two demo-usable scenarios are registered. The other agents (investment, cyber,
  // lending, and the crypto/device/child-safety mini-suite) were measurement exercises that
  // ended in parity with web search — their write-ups live in docs/DEMO.md and their source
  // files remain in the repo, but they are intentionally NOT registered so Studio shows only
  // what actually demos. To bring one back, re-add its import and registry entry.
  agents: {
    // Scenario 1 — regulatory grounding (what a body is, and what it published). Same model,
    // same base prompt; the only difference is the Carver data. See docs/DEMO.md "Beat 1-4".
    baselineAgent,
    carverAgent,
    // Winning scenario — state-lending counterfactual swap. A loan denied by an automated model,
    // the applicant's state swapped CO/CA/NY: the grounded arm surfaces the state obligation
    // (CO AI Act, CA Holden Act) that baseline and web search both miss. Run with
    // scripts/state-lending-probe.mjs. See docs/DEMO.md "The state-lending counterfactual swap".
    advisorBaselineAgent,
    advisorWebsearchAgent,
    stateLendingCarverAgent,
  },
  // Storage + observability are what make Studio's Traces view work;
  // without them the exporter disables itself and traces are never persisted.
  storage: new LibSQLStore({
    id: 'mastra-storage',
    url: 'file:./mastra.db',
  }),
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
