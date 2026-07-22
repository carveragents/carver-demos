/**
 * The crypto-asset-domain search and structured-query tools.
 *
 * Same machinery as the enforcement tool — only the domain id differs. Config lives in
 * data/carver-domains.json.
 */
import { createDomainQueryTool, createDomainSearchTool, findDomain } from './carver-domain-tool.ts';

export const cryptoDomain = findDomain('crypto-assets');
export const searchCarverCrypto = createDomainSearchTool(cryptoDomain);
export const queryCarverCrypto = createDomainQueryTool(cryptoDomain);
