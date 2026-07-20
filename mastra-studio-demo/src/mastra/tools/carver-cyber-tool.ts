/**
 * The cybersecurity-domain search tool.
 *
 * Same machinery as the enforcement tool — only the domain id differs. Config lives in
 * data/carver-domains.json.
 */
import { createDomainSearchTool, findDomain } from './carver-domain-tool.ts';

export const cyberDomain = findDomain('cyber');
export const searchCarverCyber = createDomainSearchTool(cyberDomain);
