import { NextResponse, type NextRequest } from 'next/server'
import type { Firestore } from 'firebase-admin/firestore'

/**
 * Extract the customer id from the `Authorization` header, validate it
 * against the `customers` collection, and return the customer document
 * data (or `false` when invalid).
 */
export async function validateCustomer(
  req: NextRequest,
  db: Firestore,
): Promise<{ id: string; data: Record<string, unknown> } | false> {
  const token = req.headers.get('authorization')
  if (!token) return false
  try {
    const doc = await db.collection('customers').doc(token).get()
    if (!doc.exists) return false
    return { id: doc.id, data: (doc.data() as Record<string, unknown>) ?? {} }
  } catch (err) {
    console.error('[bonarjs-sdk-alpha/server] customer validation failed:', err)
    return false
  }
}

/** 401 helper for invalid customer tokens. */
export function invalidCustomerResponse(): NextResponse {
  return NextResponse.json({ error: 'Invalid token.' }, { status: 401 })
}
