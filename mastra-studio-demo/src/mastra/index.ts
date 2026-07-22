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
import { cyberWebsearchAgent } from './agents/cyber-websearch-agent.ts';
import { lendingBaselineAgent } from './agents/lending-baseline-agent.ts';
import { lendingCarverAgent } from './agents/lending-carver-agent.ts';
import { lendingWebsearchAgent } from './agents/lending-websearch-agent.ts';
import { advisorBaselineAgent } from './agents/advisor-baseline-agent.ts';
import { advisorWebsearchAgent } from './agents/advisor-websearch-agent.ts';
import { cryptoCarverAgent } from './agents/crypto-carver-agent.ts';
import { deviceCarverAgent } from './agents/device-carver-agent.ts';
import { childSafetyCarverAgent } from './agents/child-safety-carver-agent.ts';
import { stateLendingCarverAgent } from './agents/state-lending-carver-agent.ts';
import { websearchAgent } from './agents/websearch-agent.ts';

export const mastra = new Mastra({
  // The demo is the contrast: same model, same base prompt, one has Carver data.
  // Two contrast pairs: regulatory (baseline/carver) and investment (investmentBaseline/investmentCarver).
  agents: {
    baselineAgent,
    carverAgent,
    websearchAgent,
    investmentBaselineAgent,
    investmentCarverAgent,
    cyberBaselineAgent,
    cyberCarverAgent,
    cyberWebsearchAgent,
    lendingBaselineAgent,
    lendingCarverAgent,
    lendingWebsearchAgent,
    // Cross-domain silent-trigger mini-suite: two shared arms (advisorBaseline/advisorWebsearch)
    // plus one grounded arm per sector. See scripts/trigger-probe.mjs.
    advisorBaselineAgent,
    advisorWebsearchAgent,
    cryptoCarverAgent,
    deviceCarverAgent,
    childSafetyCarverAgent,
    // State-lending counterfactual swap: does the grounded arm track obligations that vary by
    // the applicant's state (CO AI Act, CA Holden Act) where baseline/web give the federal answer?
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
