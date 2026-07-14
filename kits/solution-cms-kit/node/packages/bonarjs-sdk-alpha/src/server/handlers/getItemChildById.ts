import { NextResponse, type NextRequest } from 'next/server'

import { createGuardRead } from '../middleware/authGuard'
import { serializeTimestamps } from '../utils/serializeTimestamps'
import { invalidCustomerResponse, validateCustomer } from './shared'
import type { HandlerDeps } from './types'

/**
 * Factory for the `POST /api/tables/getItemChildById` route handler.
 *
 * Reads a document from a subcollection:
 * `tables/{customerId}/{table}/items/{itemId}/{childName}/{childId}`
 */
export function makeGetItemChildById(deps: HandlerDeps) {
  const guardRead = createGuardRead({ appCheck: deps.appCheck })

  return async function POST(req: NextRequest): Promise<NextResponse> {
    const appCheckError = await guardRead(req)
    if (appCheckError) return appCheckError

    const customer = await validateCustomer(req, deps.db)
    if (!customer) return invalidCustomerResponse()

    const body = (await req.json()) as {
      table?: string
      item?: string
      childName?: string
      childId?: string
    }

    if (!body.table || !body.item || !body.childName || !body.childId) {
      return NextResponse.json(
        { error: 'Missing table, item, childName, or childId.' },
        { status: 400 },
      )
    }

    try {
      const snap = await deps.db
        .collection('tables')
        .doc(customer.id)
        .collection(body.table)
        .doc(body.item)
        .collection(body.childName)
        .doc(body.childId)
        .get()

      if (!snap.exists) {
        return NextResponse.json(
          { error: 'Child document not found.' },
          { status: 404 },
        )
      }

      return NextResponse.json(
        { content: serializeTimestamps(snap.data()) },
        { status: 201 },
      )
    } catch (err) {
      console.error(
        '[bonarjs-sdk-alpha/server] getItemChildById failed:',
        err,
      )
      return NextResponse.json(
        { error: err instanceof Error ? err.message : 'Unknown error' },
        { status: 500 },
      )
    }
  }
}
