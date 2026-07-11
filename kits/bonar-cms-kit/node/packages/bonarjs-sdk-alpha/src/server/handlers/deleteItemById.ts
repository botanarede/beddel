import { NextResponse, type NextRequest } from 'next/server'

import { createGuardWrite } from '../middleware/authGuard'
import { invalidCustomerResponse, validateCustomer } from './shared'
import type { HandlerDeps } from './types'

/**
 * Factory for the `POST /api/tables/deleteItemById` route handler.
 *
 * Performs a soft delete: copies the document to
 * `tables/{customer}/archived/{table}/items/{id}` with `archived: true`
 * and `archivedAt: <iso>` before deleting the original.
 */
export function makeDeleteItemById(deps: HandlerDeps) {
  const guardWrite = createGuardWrite({
    appCheck: deps.appCheck,
    auth: deps.auth,
  })
  const now = deps.now ?? (() => new Date())

  return async function POST(req: NextRequest): Promise<NextResponse> {
    const authResult = await guardWrite(req)
    if (authResult instanceof NextResponse) return authResult

    const customer = await validateCustomer(req, deps.db)
    if (!customer) return invalidCustomerResponse()

    const body = (await req.json()) as { table?: string; id?: string }
    if (!body.table || !body.id) {
      return NextResponse.json(
        { error: 'Missing table or id.' },
        { status: 400 },
      )
    }

    const clientRef = deps.db.collection('tables').doc(customer.id)
    const documentRef = clientRef.collection(body.table).doc(body.id)

    try {
      const snap = await documentRef.get()
      if (!snap.exists) {
        return NextResponse.json(
          { error: 'Document not found.' },
          { status: 404 },
        )
      }

      const data = snap.data() ?? {}
      const archivedRef = clientRef
        .collection('archived')
        .doc(body.table)
        .collection('items')
        .doc(body.id)

      await archivedRef.set({
        ...data,
        archived: true,
        archivedAt: now().toISOString(),
      })
      await documentRef.delete()

      return NextResponse.json({ success: true }, { status: 200 })
    } catch (err) {
      console.error('[bonarjs-sdk-alpha/server] deleteItemById failed:', err)
      return NextResponse.json(
        { error: err instanceof Error ? err.message : 'Unknown error' },
        { status: 500 },
      )
    }
  }
}
