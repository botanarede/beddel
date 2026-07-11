import type { NextRequest } from 'next/server'
import { NextResponse } from 'next/server'

/** Default list of tables that accept anonymous writes. */
export const DEFAULT_PUBLIC_SUBMIT_TABLES: readonly string[] = [
  'emails',
  'reservas',
]

/** Verified user payload returned by {@link guardWrite}. */
export interface VerifiedUser {
  uid: string
  email: string
  customer: string
}

/** Contract for the `verifyToken` call — kept minimal to avoid coupling. */
export interface AppCheckVerifier {
  verifyToken(token: string): Promise<unknown>
}

/** Contract for the `verifyIdToken` call — kept minimal to avoid coupling. */
export interface AuthVerifier {
  verifyIdToken(token: string): Promise<{
    uid: string
    email?: string
    customer?: unknown
    [key: string]: unknown
  }>
}

/** Dependencies shared by every guard. */
export interface AuthGuardDeps {
  appCheck: AppCheckVerifier
  auth: AuthVerifier
  publicSubmitTables?: readonly string[]
}

/** Create a read guard (App Check only). */
export function createGuardRead(deps: { appCheck: AppCheckVerifier }) {
  return async function guardRead(
    req: NextRequest,
  ): Promise<NextResponse | null> {
    const token = req.headers.get('x-firebase-appcheck')
    if (!token) {
      return NextResponse.json(
        { error: 'Missing App Check token.' },
        { status: 401 },
      )
    }
    try {
      await deps.appCheck.verifyToken(token)
      return null
    } catch (err) {
      console.error('[auth-guard] App Check verification failed:', err)
      return NextResponse.json(
        { error: 'Invalid App Check token.' },
        { status: 401 },
      )
    }
  }
}

/** Create a write guard (App Check + Firebase ID Token). */
export function createGuardWrite(deps: {
  appCheck: AppCheckVerifier
  auth: AuthVerifier
}) {
  const guardRead = createGuardRead(deps)
  return async function guardWrite(
    req: NextRequest,
  ): Promise<NextResponse | VerifiedUser> {
    const appCheckError = await guardRead(req)
    if (appCheckError) return appCheckError

    const idToken = req.headers.get('x-firebase-idtoken')
    if (!idToken) {
      return NextResponse.json(
        { error: 'Authentication required for write operations.' },
        { status: 403 },
      )
    }

    try {
      const decoded = await deps.auth.verifyIdToken(idToken)
      return {
        uid: decoded.uid,
        email: decoded.email ?? '',
        customer: typeof decoded.customer === 'string' ? decoded.customer : '',
      }
    } catch (err) {
      console.error('[auth-guard] ID Token verification failed:', err)
      return NextResponse.json(
        { error: 'Invalid or expired authentication token.' },
        { status: 403 },
      )
    }
  }
}

/**
 * Create a table-aware smart-write guard.
 *
 * Public submit tables accept App Check only; protected tables require a
 * valid Firebase ID Token too.
 */
export function createGuardSmartWrite(deps: AuthGuardDeps) {
  const publicTables = new Set(
    deps.publicSubmitTables ?? DEFAULT_PUBLIC_SUBMIT_TABLES,
  )
  const guardRead = createGuardRead(deps)
  const guardWrite = createGuardWrite(deps)
  return async function guardSmartWrite(
    req: NextRequest,
    table: string,
  ): Promise<NextResponse | VerifiedUser | null> {
    if (publicTables.has(table)) return guardRead(req)
    return guardWrite(req)
  }
}

/** Returns true when `table` is in the public-submit allow-list. */
export function isPublicSubmitTable(
  table: string,
  publicSubmitTables: readonly string[] = DEFAULT_PUBLIC_SUBMIT_TABLES,
): boolean {
  return publicSubmitTables.includes(table)
}
