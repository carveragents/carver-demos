/**
 * The cybersecurity-domain search and structured-query tools.
 *
 * Same machinery as the enforcement tool — only the domain id differs. Config lives in
 * data/carver-domains.json.
 */
import { createDomainQueryTool, createDomainSearchTool, findDomain } from './carver-domain-tool.ts';

export const cyberDomain = findDomain('cyber');
export const searchCarverCyber = createDomainSearchTool(cyberDomain);
export const queryCarverCyber = createDomainQueryTool(cyberDomain);
