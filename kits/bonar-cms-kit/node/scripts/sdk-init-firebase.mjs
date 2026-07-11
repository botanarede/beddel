/**
 * sdk-init-firebase.mjs — Initialize Firebase Admin SDK via bonarjs-sdk-alpha.
 *
 * Usage: node scripts/sdk-init-firebase.mjs <project_id>
 *
 * Outputs JSON: { "success": true, "project_id": "<id>", "initialized": true }
 * On error outputs: { "success": false, "error": "<message>" } and exits 1.
 *
 * Environment:
 *   GOOGLE_APPLICATION_CREDENTIALS — path to service account JSON (optional,
 *     falls back to ADC).
 *   FIREBASE_SERVICE_ACCOUNT_JSON — stringified service account JSON (optional).
 */

import { initAdmin } from '@botanarede/bonarjs-sdk-alpha/server'

const projectId = process.argv[2]

if (!projectId) {
  console.log(JSON.stringify({ success: false, error: 'Missing project_id argument' }))
  process.exit(1)
}

try {
  const config = {
    projectId,
    serviceAccountJson: process.env.FIREBASE_SERVICE_ACCOUNT_JSON || undefined,
  }

  await initAdmin(config)

  console.log(JSON.stringify({
    success: true,
    project_id: projectId,
    initialized: true,
  }))
} catch (err) {
  console.log(JSON.stringify({
    success: false,
    error: err instanceof Error ? err.message : String(err),
  }))
  process.exit(1)
}
