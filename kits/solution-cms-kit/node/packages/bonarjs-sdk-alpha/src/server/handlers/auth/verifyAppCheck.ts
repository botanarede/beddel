import { NextResponse, type NextRequest } from 'next/server'

import { invalidCustomerResponse, validateCustomer } from '../shared'
import type { AuthHandlerDeps } from './types'

/**
 * Factory for the `POST /api/auth/verifyAppCheck` route handler.
 *
 * Validates the customer API key, then generates a server-side App Check
 * token using the Firebase Admin SDK. The client uses this token for
 * subsequent requests that require App Check verification.
 *
 * Preserves the legacy response envelope for backward compatibility:
 * `{ token, ttlMillis }` with status 201.
 */
export function makeVerifyAppCheck(deps: AuthHandlerDeps) {
  return async function POST(req: NextRequest): Promise<NextResponse> {
    const customer = await validateCustomer(req, deps.db)
    if (!customer) return invalidCustomerResponse()

    try {
      const result = await deps.appCheckIssuer.createToken(deps.appId, {
        ttlMillis: 3_600_000, // 1 hour
      })

      return NextResponse.json(
        { token: result.token, ttlMillis: result.ttlMillis },
        { status: 201 },
      )
    } catch (err) {
      console.error(
        '[bonarjs-sdk-alpha/server] App Check token creation failed:',
        err,
      )
      return NextResponse.json(
        { error: 'Failed to generate App Check token.' },
        { status: 500 },
      )
    }
  }
}
