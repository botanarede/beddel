/**
 * sdk-clear-cache.mjs — Remove cached JSON files for a tenant (or all tenants).
 *
 * Usage: node scripts/sdk-clear-cache.mjs [tenant_id]
 *
 * If tenant_id is provided, removes only that tenant's cache directory.
 * If omitted, removes ALL cached files (the entire cache/ directory contents).
 *
 * Outputs JSON: { "success": true, "cleared_count": <number> }
 * On error outputs: { "success": false, "error": "<message>" } and exits 1.
 */

import { rmSync, readdirSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const CACHE_DIR = join(__dirname, '..', 'cache')

const tenantId = process.argv[2] || null

try {
  let clearedCount = 0

  if (!existsSync(CACHE_DIR)) {
    console.log(JSON.stringify({ success: true, cleared_count: 0 }))
    process.exit(0)
  }

  if (tenantId) {
    // Clear specific tenant cache
    const tenantCacheDir = join(CACHE_DIR, tenantId)
    if (existsSync(tenantCacheDir)) {
      const files = readdirSync(tenantCacheDir)
      clearedCount = files.length
      rmSync(tenantCacheDir, { recursive: true, force: true })
    }
  } else {
    // Clear all caches
    const entries = readdirSync(CACHE_DIR)
    for (const entry of entries) {
      const entryPath = join(CACHE_DIR, entry)
      rmSync(entryPath, { recursive: true, force: true })
      clearedCount += 1
    }
  }

  console.log(JSON.stringify({ success: true, cleared_count: clearedCount }))
} catch (err) {
  console.log(JSON.stringify({
    success: false,
    error: err instanceof Error ? err.message : String(err),
  }))
  process.exit(1)
}
