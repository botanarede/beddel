import { NextResponse, type NextRequest } from 'next/server'

import { createGuardRead } from '../middleware/authGuard'
import { serializeTimestamps } from '../utils/serializeTimestamps'
import { invalidCustomerResponse, validateCustomer } from './shared'
import type { HandlerDeps } from './types'

/**
 * Factory for the `POST /api/tables/getItems` route handler.
 *
 * The resulting handler preserves the legacy response envelope
 * (`{ content }`) and the legacy status codes (201 on hit, 201+`{}` on
 * empty, 500 on unhandled error).
 */
export function makeGetItems(deps: HandlerDeps) {
  const guardRead = createGuardRead({ appCheck: deps.appCheck })

  return async function POST(req: NextRequest): Promise<NextResponse> {
    const appCheckError = await guardRead(req)
    if (appCheckError) return appCheckError

    const customer = await validateCustomer(req, deps.db)
    if (!customer) return invalidCustomerResponse()

    const body = (await req.json()) as {
      table?: string
      queryOptions?: {
        where?: { field: string; op: FirebaseFirestore.WhereFilterOp; value: unknown }
        orderBy?: { field: string; direction?: FirebaseFirestore.OrderByDirection }
        limit?: number
      }
    }

    const { table, queryOptions } = body
    if (!table) {
      return NextResponse.json({ error: 'Missing table.' }, { status: 400 })
    }

    try {
      let query: FirebaseFirestore.Query = deps.db.collection(
        `tables/${customer.id}/${table}`,
      )

      if (queryOptions?.where) {
        const { field, op, value } = queryOptions.where
        query = query.where(field, op, value)
      }
      if (queryOptions?.orderBy) {
        const { field, direction } = queryOptions.orderBy
        query = query.orderBy(field, direction ?? 'asc')
      }
      if (queryOptions?.limit) {
        query = query.limit(queryOptions.limit)
      }

      const snapshot = await query.get()
      if (snapshot.empty) {
        return NextResponse.json({ content: {} }, { status: 201 })
      }

      const data = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...serializeTimestamps(doc.data()),
      }))
      return NextResponse.json({ content: data }, { status: 201 })
    } catch (err) {
      console.error('[bonarjs-sdk-alpha/server] getItems failed:', err)
      return NextResponse.json(
        { error: err instanceof Error ? err.message : 'Unknown error' },
        { status: 500 },
      )
    }
  }
}
