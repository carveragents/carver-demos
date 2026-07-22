/**
 * The online-child-safety-domain search and structured-query tools.
 *
 * Same machinery as the enforcement tool — only the domain id differs. Config lives in
 * data/carver-domains.json.
 */
import { createDomainQueryTool, createDomainSearchTool, findDomain } from './carver-domain-tool.ts';

export const childSafetyDomain = findDomain('child-safety');
export const searchCarverChildSafety = createDomainSearchTool(childSafetyDomain);
export const queryCarverChildSafety = createDomainQueryTool(childSafetyDomain);
