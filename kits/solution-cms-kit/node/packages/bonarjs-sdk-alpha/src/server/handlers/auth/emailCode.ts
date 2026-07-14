import { NextResponse, type NextRequest } from 'next/server'
import type { Firestore } from 'firebase-admin/firestore'

import { invalidCustomerResponse, validateCustomer } from '../shared'
import type { AuthHandlerDeps } from './types'

/** Generate a random 6-digit verification code. */
function generateCode(): string {
  return Math.floor(100000 + Math.random() * 900000).toString()
}

/**
 * Find or create a user in both Firebase Auth and the `users` Firestore
 * collection. Returns the Firestore document ID.
 */
async function ensureUser(
  email: string,
  customerUid: string,
  deps: AuthHandlerDeps,
): Promise<string> {
  const usersSnap = await deps.db
    .collection('users')
    .where('email', '==', email)
    .get()

  if (!usersSnap.empty) {
    return usersSnap.docs[0]!.id
  }

  // User does not exist — create in Auth and Firestore
  const { uid } = await deps.adminAuth.createUser({
    email,
    emailVerified: false,
  })

  const now = deps.now?.() ?? new Date()
  await deps.db.collection('users').doc(uid).set({
    email,
    apps: [customerUid],
    createdAt: now,
    lastLogin: now,
    uid,
  })

  return uid
}

/**
 * Factory for the `POST /api/auth` route handler.
 *
 * Two-phase email code authentication flow:
 * - `{ email }` → generates a 6-digit code, stores it, sends via email
 * - `{ email, code }` → verifies code, creates custom token, returns it
 *
 * Preserves the legacy response envelope for backward compatibility.
 */
export function makeEmailCodeAuth(deps: AuthHandlerDeps) {
  return async function POST(req: NextRequest): Promise<NextResponse> {
    const customer = await validateCustomer(req, deps.db)
    if (!customer) return invalidCustomerResponse()

    const { email, code } = (await req.json()) as {
      email?: string
      code?: string
    }

    if (!email) {
      return NextResponse.json(
        { error: 'Email is required.' },
        { status: 400 },
      )
    }

    const userId = await ensureUser(email, customer.id, deps)

    if (code) {
      // --- Phase 2: Verify code and issue token ---
      return handleVerifyCode(email, code, userId, customer.id, deps)
    } else {
      // --- Phase 1: Generate and send code ---
      return handleSendCode(email, userId, customer.id, deps)
    }
  }
}

async function handleVerifyCode(
  email: string,
  code: string,
  userId: string,
  customerUid: string,
  deps: AuthHandlerDeps,
): Promise<NextResponse> {
  try {
    const codeSnap = await deps.db
      .collection('verification_codes')
      .where('email', '==', email)
      .where('code', '==', code)
      .orderBy('createdAt', 'desc')
      .limit(1)
      .get()

    if (codeSnap.empty) {
      return NextResponse.json(
        { error: 'Invalid or expired code.' },
        { status: 401 },
      )
    }

    // Look up the user doc to get the auth UID
    const userSnap = await deps.db
      .collection('users')
      .where('email', '==', email)
      .limit(1)
      .get()

    if (userSnap.empty) {
      return NextResponse.json(
        { error: 'User not found.' },
        { status: 401 },
      )
    }

    const userData = userSnap.docs[0]!.data()
    const authUid = (userData.uid as string) ?? userId

    // Mark email as verified
    await deps.adminAuth.updateUser(authUid, { emailVerified: true })

    // Update last login
    const now = deps.now?.() ?? new Date()
    await deps.db.collection('users').doc(userId).update({ lastLogin: now })

    // Generate custom token with customer claim
    const customToken = await deps.adminAuth.createCustomToken(authUid, {
      customer: customerUid,
    })

    // Delete the used code
    await codeSnap.docs[0]!.ref.delete()

    return NextResponse.json({ token: customToken }, { status: 201 })
  } catch (err) {
    console.error('[bonarjs-sdk-alpha/server] email code verify failed:', err)
    return NextResponse.json(
      { error: 'Code verification failed.' },
      { status: 500 },
    )
  }
}

async function handleSendCode(
  email: string,
  userId: string,
  customerUid: string,
  deps: AuthHandlerDeps,
): Promise<NextResponse> {
  const code = generateCode()

  try {
    await deps.emailSender.send(
      email,
      'Your Access Code',
      `
        <p>Hello,</p>
        <br />
        <p>You requested an access code. Use the code below to proceed:</p>
        <br />
        <h2 style="text-align: center">${code}</h2>
        <br />
        <p>If you did not request this code, please ignore this email.</p>
        <br />
        <p>Best regards,<br>Support Team</p>
      `,
    )
  } catch (err) {
    console.error('[bonarjs-sdk-alpha/server] email send failed:', err)
    return NextResponse.json(
      { error: 'Failed to send email.' },
      { status: 500 },
    )
  }

  // Store the code in Firestore
  const now = deps.now?.() ?? new Date()
  await deps.db.collection('verification_codes').add({
    uid: userId,
    code,
    email,
    customerUid,
    createdAt: now,
  })

  return NextResponse.json({ message: 'Code sent.' }, { status: 201 })
}
