import { NextResponse, type NextRequest } from 'next/server'

import { invalidCustomerResponse, validateCustomer } from '../shared'
import type { AuthHandlerDeps } from './types'

/**
 * Factory for the `POST /api/auth/checkUserInDatabase` route handler.
 *
 * Checks if a user with the given email exists in Firebase Auth and the
 * `users` Firestore collection. If the user exists in Auth but not in
 * Firestore, creates the Firestore document.
 *
 * Preserves the legacy response envelope for backward compatibility:
 * `{ message: true }` with status 201 on success.
 */
export function makeCheckUserInDatabase(deps: AuthHandlerDeps) {
  return async function POST(req: NextRequest): Promise<NextResponse> {
    const customer = await validateCustomer(req, deps.db)
    if (!customer) return invalidCustomerResponse()

    const { email } = (await req.json()) as { email?: string }

    if (!email) {
      return NextResponse.json(
        { error: 'Email is required.' },
        { status: 400 },
      )
    }

    try {
      // Check if user exists in Firebase Auth
      const authUser = await deps.adminAuth.getUserByEmail(email)

      if (!authUser) {
        return NextResponse.json(
          { error: 'User not found.' },
          { status: 401 },
        )
      }

      // Ensure user doc exists in Firestore
      const userSnap = await deps.db
        .collection('users')
        .where('email', '==', email)
        .get()

      if (userSnap.empty) {
        const now = deps.now?.() ?? new Date()
        await deps.db.collection('users').add({
          email,
          apps: [customer.id],
          uid: authUser.uid,
          createdAt: now,
        })
      }

      return NextResponse.json({ message: true }, { status: 201 })
    } catch (err) {
      console.error(
        '[bonarjs-sdk-alpha/server] checkUserInDatabase failed:',
        err,
      )
      return NextResponse.json(
        { error: 'Failed to check user.' },
        { status: 500 },
      )
    }
  }
}
