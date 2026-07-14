/**
 * Firebase Admin bootstrap utilities for the API host app.
 *
 * These functions initialize `firebase-admin` and wire the real Admin SDK
 * services into the narrow SDK interfaces (`HandlerDeps`, `AuthHandlerDeps`).
 *
 * IMPORTANT: This module imports `firebase-admin` — it must only be used
 * in server-side code (API routes, middleware), never in client bundles.
 */

import type { App } from 'firebase-admin/app'
import type { Firestore } from 'firebase-admin/firestore'
import type { Auth } from 'firebase-admin/auth'

import type { AppCheckVerifier, AuthVerifier } from './middleware/authGuard'
import type { HandlerDeps } from './handlers/types'
import type {
  AuthHandlerDeps,
  AdminAuth,
  AppCheckIssuer,
  EmailSender,
} from './handlers/auth/types'
import type { TimestampFactory } from './utils/normalizeTimestamps'

/** Configuration for the Firebase Admin bootstrap. */
export interface BootstrapConfig {
  /** Stringified JSON of the service account key. */
  serviceAccountJson?: string
  /** Firebase project ID. */
  projectId: string
  /** Firebase Storage bucket. */
  storageBucket?: string
}

/** Extended config for auth handler deps. */
export interface AuthBootstrapConfig extends BootstrapConfig {
  /** Firebase App ID for App Check token creation. */
  appId: string
  /** Email sender implementation. */
  emailSender: EmailSender
  /** Tables that accept anonymous writes. */
  publicSubmitTables?: readonly string[]
}

/** Singleton state. */
let _app: App | null = null
let _db: Firestore | null = null
let _auth: Auth | null = null

/**
 * Initialize Firebase Admin SDK (singleton).
 * Lazy-imports `firebase-admin` to avoid module-load-time side effects.
 */
export async function initAdmin(config: BootstrapConfig): Promise<{
  app: App
  db: Firestore
  auth: Auth
}> {
  if (_app && _db && _auth) {
    return { app: _app, db: _db, auth: _auth }
  }

  // Dynamic imports to keep firebase-admin out of the module graph
  // until actually needed (reduces cold start impact).
  const { getApps, initializeApp, cert } = await import('firebase-admin/app')
  const { getFirestore } = await import('firebase-admin/firestore')
  const { getAuth } = await import('firebase-admin/auth')

  if (getApps().length === 0) {
    const credential = config.serviceAccountJson
      ? cert(JSON.parse(config.serviceAccountJson))
      : undefined // Falls back to GOOGLE_APPLICATION_CREDENTIALS

    _app = initializeApp({
      credential,
      projectId: config.projectId,
      storageBucket: config.storageBucket,
    })
  } else {
    const { getApp } = await import('firebase-admin/app')
    _app = getApp()
  }

  _db = getFirestore(_app)
  _auth = getAuth(_app)

  return { app: _app, db: _db, auth: _auth }
}

/**
 * Create base `HandlerDeps` for CRUD route handlers.
 */
export async function createHandlerDeps(
  config: BootstrapConfig & { publicSubmitTables?: readonly string[] },
): Promise<HandlerDeps> {
  const { db, auth } = await initAdmin(config)
  const { getAppCheck } = await import('firebase-admin/app-check')
  const { Timestamp } = await import('firebase-admin/firestore')

  const appCheck: AppCheckVerifier = getAppCheck()
  const authVerifier: AuthVerifier = {
    verifyIdToken: async (token: string) => {
      const decoded = await auth.verifyIdToken(token)
      return {
        uid: decoded.uid,
        email: decoded.email,
        customer: decoded.customer,
      }
    },
  }

  return {
    db,
    appCheck,
    auth: authVerifier,
    timestampFactory: Timestamp as unknown as TimestampFactory,
    publicSubmitTables: config.publicSubmitTables,
  }
}

/**
 * Create `AuthHandlerDeps` for auth route handlers.
 * Extends base deps with admin auth, App Check issuance, and email sending.
 */
export async function createAuthHandlerDeps(
  config: AuthBootstrapConfig,
): Promise<AuthHandlerDeps> {
  const baseDeps = await createHandlerDeps(config)
  const { auth } = await initAdmin(config)
  const { getAppCheck } = await import('firebase-admin/app-check')

  const adminAuth: AdminAuth = {
    createUser: async (props) => {
      const record = await auth.createUser(props)
      return { uid: record.uid }
    },
    createCustomToken: (uid, claims) => auth.createCustomToken(uid, claims),
    getUserByEmail: async (email) => {
      try {
        const record = await auth.getUserByEmail(email)
        return { uid: record.uid, email: record.email }
      } catch (err: unknown) {
        // Only swallow user-not-found; re-throw unexpected errors
        if (
          typeof err === 'object' &&
          err !== null &&
          'code' in err &&
          (err as { code: string }).code === 'auth/user-not-found'
        ) {
          return null
        }
        throw err
      }
    },
    updateUser: async (uid, props) => {
      await auth.updateUser(uid, props)
    },
  }

  const appCheckIssuer: AppCheckIssuer = {
    createToken: async (appId, options) => {
      const appCheck = getAppCheck()
      const result = await appCheck.createToken(appId, {
        ttlMillis: options?.ttlMillis ?? 3_600_000,
      })
      return { token: result.token, ttlMillis: result.ttlMillis }
    },
  }

  return {
    ...baseDeps,
    adminAuth,
    appCheckIssuer,
    emailSender: config.emailSender,
    appId: config.appId,
  }
}
