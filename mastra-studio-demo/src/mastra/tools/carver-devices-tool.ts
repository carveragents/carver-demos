/**
 * The medical-device-domain search and structured-query tools.
 *
 * Same machinery as the enforcement tool — only the domain id differs. Config lives in
 * data/carver-domains.json.
 */
import { createDomainQueryTool, createDomainSearchTool, findDomain } from './carver-domain-tool.ts';

export const devicesDomain = findDomain('medical-devices');
export const searchCarverDevices = createDomainSearchTool(devicesDomain);
export const queryCarverDevices = createDomainQueryTool(devicesDomain);
