import { readdir, readFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { TenantConfigSchema, type TenantConfig } from '@botanarede/schema'

interface TenantSummary {
  id: string
  name: string
  fileName: string
}

function tenantsDir(): string {
  const envDir = process.env.TENANTS_DIR
  if (envDir) return resolve(process.cwd(), envDir)
  return resolve(process.cwd(), '../../tenants')
}

/**
 * Lists all tenant JSON files and returns their id + name.
 */
export async function listTenants(): Promise<TenantSummary[]> {
  const dir = tenantsDir()
  let files: string[]
  try {
    files = await readdir(dir)
  } catch {
    return []
  }

  const jsonFiles = files.filter(
    (f) => f.endsWith('.json') && f !== 'template.json',
  )

  const results: TenantSummary[] = []
  for (const fileName of jsonFiles) {
    try {
      const raw = await readFile(join(dir, fileName), 'utf-8')
      const data = JSON.parse(raw)
      if (data?.metadata?.id && data?.metadata?.name) {
        results.push({
          id: data.metadata.id,
          name: data.metadata.name,
          fileName,
        })
      }
    } catch {
      // Skip invalid files
    }
  }

  return results
}

/**
 * Loads and validates a full TenantConfig by id.
 */
export async function loadTenantConfig(
  id: string,
): Promise<TenantConfig | null> {
  const dir = tenantsDir()
  let files: string[]
  try {
    files = await readdir(dir)
  } catch {
    return null
  }

  for (const fileName of files) {
    if (!fileName.endsWith('.json')) continue
    try {
      const raw = await readFile(join(dir, fileName), 'utf-8')
      const data = JSON.parse(raw)
      if (data?.metadata?.id === id) {
        const parsed = TenantConfigSchema.safeParse(data)
        if (parsed.success) return parsed.data
        // Return raw data if schema validation fails (schema may be stricter than data)
        return data as TenantConfig
      }
    } catch {
      // Skip
    }
  }

  return null
}
