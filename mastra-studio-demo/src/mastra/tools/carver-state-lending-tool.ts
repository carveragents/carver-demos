/**
 * The state-lending-domain search and structured-query tools, over the curated federal+state
 * adverse-action obligation index (built by scripts/build-curated-index.mjs). Same machinery
 * as the other domain tools; config lives in data/carver-domains.json.
 */
import { createDomainQueryTool, createDomainSearchTool, findDomain } from './carver-domain-tool.ts';

export const stateLendingDomain = findDomain('state-lending');
export const searchCarverStateLending = createDomainSearchTool(stateLendingDomain);
export const queryCarverStateLending = createDomainQueryTool(stateLendingDomain);
