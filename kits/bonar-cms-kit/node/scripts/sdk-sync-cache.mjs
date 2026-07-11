/**
 * sdk-sync-cache.mjs — Sync tenant data from Firestore to local JSON cache.
 *
 * Usage: node scripts/sdk-sync-cache.mjs <tenant_id>
 *
 * Outputs JSON: { "success": true, "tenant_id": "<id>", "cached_files": ["<path>", ...] }
 * On error outputs: { "success": false, "error": "<message>" } and exits 1.
 *
 * Reads Firestore collections for the specified tenant and writes them to
 * local JSON files at <kit_root>/node/cache/<tenant_id>/.
 *
 * Environment:
 *   GOOGLE_APPLICATION_CREDENTIALS — path to service account JSON.
 *   FIREBASE_PROJECT_ID — Firebase project ID.
 *   FIREBASE_SERVICE_ACCOUNT_JSON — stringified service account JSON (optional).
 */

import { initAdmin } from '@botanarede/bonarjs-sdk-alpha/server'
import { writeFileSync, mkdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const CACHE_DIR = join(__dirname, '..', 'cache')

const tenantId = process.argv[2]

if (!tenantId) {
  console.log(JSON.stringify({ success: false, error: 'Missing tenant_id argument' }))
  process.exit(1)
}

try {
  const projectId = process.env.FIREBASE_PROJECT_ID
  if (!projectId) {
    throw new Error('FIREBASE_PROJECT_ID environment variable is required')
  }

  const config = {
    projectId,
    serviceAccountJson: process.env.FIREBASE_SERVICE_ACCOUNT_JSON || undefined,
  }

  const { db } = await initAdmin(config)

  // Fetch tenant data from Firestore
  const tenantDoc = await db.collection('tenants').doc(tenantId).get()
  if (!tenantDoc.exists) {
    throw new Error(`Tenant not found: ${tenantId}`)
  }

  // Create cache directory
  const tenantCacheDir = join(CACHE_DIR, tenantId)
  mkdirSync(tenantCacheDir, { recursive: true })

  const cachedFiles = []

  // Cache tenant config
  const configPath = join(tenantCacheDir, 'config.json')
  writeFileSync(configPath, JSON.stringify(tenantDoc.data(), null, 2))
  cachedFiles.push(configPath)

  // Cache tenant collections (users, content, events)
  const collections = ['users', 'content', 'events']
  for (const col of collections) {
    const snapshot = await db
      .collection('tenants')
      .doc(tenantId)
      .collection(col)
      .get()

    if (!snapshot.empty) {
      const data = snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }))
      const colPath = join(tenantCacheDir, `${col}.json`)
      writeFileSync(colPath, JSON.stringify(data, null, 2))
      cachedFiles.push(colPath)
    }
  }

  console.log(JSON.stringify({
    success: true,
    tenant_id: tenantId,
    cached_files: cachedFiles,
  }))
} catch (err) {
  console.log(JSON.stringify({
    success: false,
    error: err instanceof Error ? err.message : String(err),
  }))
  process.exit(1)
}
