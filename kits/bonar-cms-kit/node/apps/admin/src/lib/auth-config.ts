/**
 * Shared auth configuration for next-firebase-auth-edge.
 *
 * Used by middleware/proxy (edge runtime) and API routes (node runtime).
 * The service account credentials are read from env vars.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Firebase service account credentials for next-firebase-auth-edge.
 */
export interface ServiceAccountCredentials {
  projectId: string
  clientEmail: string
  privateKey: string
}

// ---------------------------------------------------------------------------
// Module-level flags (avoid repeated console warnings)
// ---------------------------------------------------------------------------

let serviceAccountParseErrorLogged = false

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const AUTH_COOKIE_NAME = '__session'

/**
 * Signature keys for cookie integrity. Must be at least 32 bytes.
 * In production, use a proper secret from Cloud Secret Manager.
 */
export const AUTH_COOKIE_SIGNATURE_KEYS = [
  process.env.AUTH_COOKIE_SECRET ?? 'CHANGE-ME-insecure-dev-only-cookie-secret',
]

// ---------------------------------------------------------------------------
// Service Account
// ---------------------------------------------------------------------------

/**
 * Read Firebase service account credentials from environment.
 *
 * - If `FIREBASE_SERVICE_ACCOUNT_JSON` is missing/empty → returns `undefined`
 * - If present but invalid JSON → logs error once, returns `undefined`
 */
export function getServiceAccount(): ServiceAccountCredentials | undefined {
  const json = process.env.FIREBASE_SERVICE_ACCOUNT_JSON

  if (!json || json.trim() === '') {
    return undefined
  }

  try {
    const parsed = JSON.parse(json) as Record<string, unknown>
    return {
      projectId: parsed.project_id as string,
      clientEmail: parsed.client_email as string,
      privateKey: parsed.private_key as string,
    }
  } catch {
    if (!serviceAccountParseErrorLogged) {
      serviceAccountParseErrorLogged = true
      console.error(
        '[auth-config] Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON.',
      )
    }
    return undefined
  }
}

// ---------------------------------------------------------------------------
// Firebase API Key
// ---------------------------------------------------------------------------

export function getFirebaseApiKey(): string {
  return process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? ''
}
