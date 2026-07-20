import { Mastra } from '@mastra/core/mastra';
import { LibSQLStore } from '@mastra/libsql';
import { PinoLogger } from '@mastra/loggers';
import { MastraStorageExporter, Observability } from '@mastra/observability';
import { baselineAgent } from './agents/baseline-agent.ts';
import { carverAgent } from './agents/carver-agent.ts';
import { investmentBaselineAgent } from './agents/investment-baseline-agent.ts';
import { investmentCarverAgent } from './agents/investment-carver-agent.ts';
import { cyberBaselineAgent } from './agents/cyber-baseline-agent.ts';
import { cyberCarverAgent } from './agents/cyber-carver-agent.ts';

export const mastra = new Mastra({
  // The demo is the contrast: same model, same base prompt, one has Carver data.
  // Two contrast pairs: regulatory (baseline/carver) and investment (investmentBaseline/investmentCarver).
  agents: {
    baselineAgent,
    carverAgent,
    investmentBaselineAgent,
    investmentCarverAgent,
    cyberBaselineAgent,
    cyberCarverAgent,
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
