import { NextResponse, type NextRequest } from 'next/server'

import { createGuardSmartWrite } from '../middleware/authGuard'
import { normalizeTimestamps } from '../utils/normalizeTimestamps'
import { serializeTimestamps } from '../utils/serializeTimestamps'
import { invalidCustomerResponse, validateCustomer } from './shared'
import type { HandlerDeps } from './types'

interface SetItemBody {
  table?: string
  id?: string
  data?: Record<string, unknown>
  events?: string
}

/**
 * Factory for the `POST /api/tables/setItem` route handler.
 *
 * The handler applies `guardSmartWrite` (App Check only for public submit
 * tables; App Check + ID Token for everything else), normalises timestamps
 * via the injected factory, and returns the complete saved document under
 * the `item` field.
 */
export function makeSetItem(deps: HandlerDeps) {
  const guardSmartWrite = createGuardSmartWrite({
    appCheck: deps.appCheck,
    auth: deps.auth,
    publicSubmitTables: deps.publicSubmitTables,
  })

  return async function POST(req: NextRequest): Promise<NextResponse> {
    const customer = await validateCustomer(req, deps.db)
    if (!customer) {
      return NextResponse.json(
        { error: 'Invalid or missing token.' },
        { status: 401 },
      )
    }

    const body = (await req.json()) as SetItemBody
    const { table, id, data, events } = body

    if (!table || !data || typeof data !== 'object') {
      return NextResponse.json(
        { error: "Missing or invalid 'table' or 'data'." },
        { status: 400 },
      )
    }

    const authResult = await guardSmartWrite(req, table)
    if (authResult instanceof NextResponse) return authResult

    const factory = deps.timestampFactory
    const sanitized = factory ? normalizeTimestamps(data, factory) : data

    try {
      const collectionRef = deps.db.collection(`tables/${customer.id}/${table}`)
      let docId: string
      let status: number

      if (id) {
        docId = id
        await collectionRef.doc(docId).set(sanitized)
        status = 200
      } else {
        const ref = await collectionRef.add(sanitized)
        docId = ref.id
        status = 201
      }

      const saved = await collectionRef.doc(docId).get()
      const docData = saved.data()

      return NextResponse.json(
        {
          message: `Document ${id ? 'updated' : 'created'} successfully.`,
          item: { id: docId, ...serializeTimestamps(docData) },
          events: events ?? 'NONE',
        },
        { status },
      )
    } catch (err) {
      console.error('[bonarjs-sdk-alpha/server] setItem failed:', err)
      return NextResponse.json(
        { error: err instanceof Error ? err.message : 'Unknown error' },
        { status: 500 },
      )
    }
  }
}
