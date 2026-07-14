import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { HttpDatabaseAdapter } from '../../../src/adapters/HttpDatabaseAdapter'
import { DatabaseError } from '../../../src/core/errors'
import type { ITokenProvider } from '../../../src/core/interfaces/ITokenProvider'

const API = 'https://api.example.com'

const tokenProvider: ITokenProvider = {
  getAppCheckToken: async () => 'ac-token',
  getIdToken: async () => 'id-token',
}

const observed: { headers?: Record<string, string>; body?: unknown } = {}

const server = setupServer(
  http.post(`${API}/api/tables/getItems`, async ({ request }) => {
    observed.headers = Object.fromEntries(request.headers.entries())
    observed.body = await request.json()
    return HttpResponse.json(
      {
        content: [
          { id: 'a', title: 'A', archived: false },
          { id: 'b', title: 'B', archived: false },
        ],
      },
      { status: 201 },
    )
  }),
  http.post(`${API}/api/tables/getItemById`, async ({ request }) => {
    observed.body = await request.json()
    return HttpResponse.json({ content: { id: 'a', title: 'A' } }, { status: 201 })
  }),
  http.post(`${API}/api/tables/setItem`, async ({ request }) => {
    observed.body = await request.json()
    return HttpResponse.json(
      {
        message: 'Document created successfully.',
        item: { id: 'new-id', title: 'Y' },
      },
      { status: 201 },
    )
  }),
  http.post(`${API}/api/tables/deleteItemById`, async () => {
    return HttpResponse.json({ success: true }, { status: 200 })
  }),
  http.post(`${API}/api/tables/getItemChildById`, async () => {
    return HttpResponse.json({ content: { id: 'child' } }, { status: 201 })
  }),
  http.post(`${API}/api/tables/error`, async () => {
    return HttpResponse.json({ error: 'boom' }, { status: 500 })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('integration/HttpDatabaseAdapter', () => {
  it('sends Authorization, AppCheck, and IdToken headers', async () => {
    const adapter = new HttpDatabaseAdapter({
      apiUrl: API,
      apiKey: 'customer-1',
      tokenProvider,
    })

    await adapter.getItems('agenda')
    expect(observed.headers?.authorization).toBe('customer-1')
    expect(observed.headers?.['x-firebase-appcheck']).toBe('ac-token')
    expect(observed.headers?.['x-firebase-idtoken']).toBe('id-token')
    expect(observed.headers?.['content-type']).toMatch(/application\/json/)
  })

  it('getItems returns the content array', async () => {
    const adapter = new HttpDatabaseAdapter({ apiUrl: API, apiKey: 'c' })
    const items = await adapter.getItems<{ id: string }>('agenda')
    expect(items.map((i) => i.id)).toEqual(['a', 'b'])
  })

  it('getItems returns [] when content is empty object', async () => {
    server.use(
      http.post(`${API}/api/tables/getItems`, () =>
        HttpResponse.json({ content: {} }, { status: 201 }),
      ),
    )
    const adapter = new HttpDatabaseAdapter({ apiUrl: API, apiKey: 'c' })
    expect(await adapter.getItems('agenda')).toEqual([])
  })

  it('forwards queryOptions when supplied', async () => {
    const adapter = new HttpDatabaseAdapter({ apiUrl: API, apiKey: 'c' })
    await adapter.getItems('agenda', { limit: 5 })
    expect((observed.body as { queryOptions?: { limit?: number } })?.queryOptions?.limit).toBe(5)
  })

  it('setItem returns the item field', async () => {
    const adapter = new HttpDatabaseAdapter({ apiUrl: API, apiKey: 'c' })
    const result = await adapter.setItem<{ id: string; title: string }>(
      'agenda',
      { title: 'Y', date: new Date('2025-01-01') },
    )
    expect(result.id).toBe('new-id')
    expect(typeof (observed.body as { data: { date: unknown } }).data.date).toBe('number')
  })

  it('deleteItemById returns { success: true }', async () => {
    const adapter = new HttpDatabaseAdapter({ apiUrl: API, apiKey: 'c' })
    expect(await adapter.deleteItemById('agenda', 'id-1')).toEqual({ success: true })
  })

  it('getItemById returns the content object', async () => {
    const adapter = new HttpDatabaseAdapter({ apiUrl: API, apiKey: 'c' })
    expect(await adapter.getItemById<{ id: string }>('agenda', 'a')).toMatchObject({
      id: 'a',
    })
  })

  it('throws DatabaseError on non-2xx', async () => {
    server.use(
      http.post(`${API}/api/tables/getItems`, () =>
        HttpResponse.json({ error: 'nope' }, { status: 401 }),
      ),
    )
    const adapter = new HttpDatabaseAdapter({ apiUrl: API, apiKey: 'c' })
    await expect(adapter.getItems('agenda')).rejects.toBeInstanceOf(DatabaseError)
  })

  it('throws DatabaseError on network failure', async () => {
    const adapter = new HttpDatabaseAdapter({
      apiUrl: 'https://does-not-exist.invalid',
      apiKey: 'c',
      fetchImpl: async () => {
        throw new Error('offline')
      },
    })
    await expect(adapter.getItems('agenda')).rejects.toBeInstanceOf(DatabaseError)
  })
})
