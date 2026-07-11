import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { HttpDatabaseAdapter } from '../../src/adapters/HttpDatabaseAdapter'
import { HttpAuthAdapter } from '../../src/adapters/HttpAuthAdapter'
import { StorageCacheAdapter } from '../../src/adapters/StorageCacheAdapter'
import { DeleteItemById } from '../../src/core/useCases/dynamicTable/DeleteItemById'
import { GetItems } from '../../src/core/useCases/dynamicTable/GetItems'
import { SetItem } from '../../src/core/useCases/dynamicTable/SetItem'
import { LoginStatus } from '../../src/core/types'
import { FakeStorage } from '../fixtures/fakeAdapters'

const API = 'https://api.example.com'
const CDN = 'https://cdn.example.com/public%2Fcache%2F{file}.json'

type Item = { id: string; title: string; date: number; archived?: boolean }
const state: { items: Item[] } = { items: [] }

const server = setupServer(
  http.post(`${API}/api/auth`, async ({ request }) => {
    const body = (await request.json()) as { email: string; code?: number }
    if (body.code === 1234) {
      return HttpResponse.json({ token: 'fake-custom-token' }, { status: 200 })
    }
    if (body.code !== undefined) {
      return HttpResponse.json({}, { status: 200 })
    }
    return HttpResponse.json({ message: 'Code sent.' }, { status: 200 })
  }),
  http.post(`${API}/api/tables/getItems`, () =>
    HttpResponse.json({ content: state.items }, { status: 201 }),
  ),
  http.post(`${API}/api/tables/setItem`, async ({ request }) => {
    const body = (await request.json()) as {
      id?: string
      data: Record<string, unknown>
    }
    const id = body.id ?? `id-${state.items.length + 1}`
    const item = { id, ...(body.data as object) } as Item
    const existing = state.items.findIndex((x) => x.id === id)
    if (existing >= 0) state.items[existing] = item
    else state.items.push(item)
    return HttpResponse.json(
      { message: 'ok', item },
      { status: body.id ? 200 : 201 },
    )
  }),
  http.post(`${API}/api/tables/deleteItemById`, async ({ request }) => {
    const body = (await request.json()) as { id: string }
    state.items = state.items.filter((x) => x.id !== body.id)
    return HttpResponse.json({ success: true }, { status: 200 })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  state.items = []
  server.resetHandlers()
})
afterAll(() => server.close())

describe('e2e/auth-crud-cache', () => {
  it('sign-in (via HTTP) → create → list → delete with cache refresh', async () => {
    const auth = new HttpAuthAdapter({ apiUrl: API, apiKey: 'customer-1' })

    const sent = await auth.signInWithEmailCode('user@example.com')
    expect(sent.message).toBe(LoginStatus.EMAIL_SENT)
    const verified = await auth.signInWithEmailCode('user@example.com', 1234)
    expect(verified.message).toBe(LoginStatus.SUCCESS)

    const storage = new FakeStorage()
    const cache = new StorageCacheAdapter({
      storage,
      bucketUrlPattern: CDN,
      publicTables: ['agenda'],
      nowMillisFn: () => new Date('2025-06-15T10:00:00Z').getTime(),
    })
    const database = new HttpDatabaseAdapter({ apiUrl: API, apiKey: 'customer-1' })

    const created = await new SetItem(database, cache).execute<Item>('agenda', {
      title: 'Show',
      date: new Date('2025-08-01').getTime(),
    })
    expect(created.id).toBeDefined()

    // allow the fire-and-forget cache refresh to complete
    await new Promise((r) => setTimeout(r, 20))
    expect(storage.uploads.some((u) => u.path === 'public/cache/agenda.json')).toBe(true)

    const items = await new GetItems(database).execute<Item>('agenda')
    expect(items).toHaveLength(1)

    await new DeleteItemById(database, cache).execute('agenda', created.id)
    await new Promise((r) => setTimeout(r, 20))

    const afterDelete = await new GetItems(database).execute<Item>('agenda')
    expect(afterDelete).toHaveLength(0)
  })
})
