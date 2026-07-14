import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { TenantConfigSchema } from '@botanarede/schema'
import {
  mapTenantToSiteConfig,
  type RuntimeSiteConfig,
  type TenantJsonExtended,
} from './tenant-types'

/**
 * Resolves tenants/ dir from the monorepo root.
 * process.cwd() in Next.js points to the app dir (src/apps/bonar-creator-studio).
 * We go up 3 levels to reach the monorepo root.
 */
function tenantsDir(): string {
  return resolve(process.cwd(), '..', '..', '..', 'tenants')
}

export function loadTenantConfig(): RuntimeSiteConfig {
  const tenantId = process.env.EXPORT_TENANT_ID || 'demo'
  const fileName = `${tenantId}.json`
  const filePath = resolve(tenantsDir(), fileName)

  let raw: string
  try {
    raw = readFileSync(filePath, 'utf-8')
  } catch (err) {
    throw new Error(
      `[load-tenant] Could not read tenant file: ${filePath}\n` +
        `Original error: ${err instanceof Error ? err.message : String(err)}`,
    )
  }

  const data: unknown = JSON.parse(raw)

  const parsed = TenantConfigSchema.safeParse(data)
  if (!parsed.success) {
    console.warn(`[load-tenant] Schema warnings for ${fileName}:`, parsed.error.format())
  }

  const tenant = data as TenantJsonExtended
  const config = mapTenantToSiteConfig(tenant)
  console.log(`[load-tenant] Loaded tenant "${tenantId}" → ${config.name}`)
  return config
}

export function loadRawTenantConfig(): TenantJsonExtended {
  const tenantId = process.env.EXPORT_TENANT_ID || 'demo'
  const filePath = resolve(tenantsDir(), `${tenantId}.json`)
  const raw = readFileSync(filePath, 'utf-8')
  return JSON.parse(raw) as TenantJsonExtended
}
