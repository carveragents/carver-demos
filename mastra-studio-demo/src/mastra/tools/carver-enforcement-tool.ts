/**
 * The enforcement-domain search tool.
 *
 * Everything that used to live here — store wiring, schemas, the degrade-on-missing-index
 * path — now lives in carver-domain-tool.ts and is shared by every domain. This file is
 * just "which domain", so adding the next one costs a two-line file like this.
 *
 * Config (index name, DB file, description) comes from data/carver-domains.json, the same
 * file the build script reads.
 */
import { createDomainSearchTool, findDomain } from './carver-domain-tool.ts';

export const enforcementDomain = findDomain('enforcement');
export const searchCarverEnforcement = createDomainSearchTool(enforcementDomain);
