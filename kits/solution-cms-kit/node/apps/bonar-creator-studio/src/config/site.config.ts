import { loadTenantConfig } from './load-tenant'

export const siteConfig = loadTenantConfig()

export type { SiteConfig } from './site-types'
