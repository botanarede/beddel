import { NextResponse, type NextRequest } from 'next/server'

import { createGuardRead } from '../middleware/authGuard'
import { serializeTimestamps } from '../utils/serializeTimestamps'
import { invalidCustomerResponse, validateCustomer } from './shared'
import type { HandlerDeps } from './types'

/**
 * Factory for the `POST /api/tables/getItemById` route handler.
 */
export function makeGetItemById(deps: HandlerDeps) {
  const guardRead = createGuardRead({ appCheck: deps.appCheck })

  return async function POST(req: NextRequest): Promise<NextResponse> {
    const appCheckError = await guardRead(req)
    if (appCheckError) return appCheckError

    const customer = await validateCustomer(req, deps.db)
    if (!customer) return invalidCustomerResponse()

    const body = (await req.json()) as { table?: string; item_id?: string }
    if (!body.table || !body.item_id) {
      return NextResponse.json(
        { error: 'Missing table or item_id.' },
        { status: 400 },
      )
    }

    try {
      const snap = await deps.db
        .collection(`tables/${customer.id}/${body.table}`)
        .doc(body.item_id)
        .get()

      if (!snap.exists) {
        return NextResponse.json(
          { error: 'Item not found.' },
          { status: 404 },
        )
      }

      return NextResponse.json(
        { content: serializeTimestamps(snap.data()) },
        { status: 201 },
      )
    } catch (err) {
      console.error('[bonarjs-sdk-alpha/server] getItemById failed:', err)
      return NextResponse.json(
        { error: err instanceof Error ? err.message : 'Unknown error' },
        { status: 500 },
      )
    }
  }
}
