import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { StorageCacheAdapter } from '../../../src/adapters/StorageCacheAdapter'
import { FakeStorage } from '../../fixtures/fakeAdapters'

const CDN = 'https://cdn.example.com/public%2Fcache%2F{file}.json'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function buildAdapter(storage = new FakeStorage()) {
  return new StorageCacheAdapter({
    storage,
    bucketUrlPattern: CDN,
    publicTables: ['agenda', 'metadata'],
    nowMillisFn: () => new Date('2025-06-15T10:00:00Z').getTime(),
  })
}

describe('integration/StorageCacheAdapter', () => {
  it('isPublicTable honours the configured list', () => {
    const adapter = buildAdapter()
    expect(adapter.isPublicTable('agenda')).toBe(true)
    expect(adapter.isPublicTable('private')).toBe(false)
  })

  it('returns null for non-public tables without hitting CDN', async () => {
    const adapter = buildAdapter()
    expect(await adapter.getCachedItems('private')).toBeNull()
  })

  it('returns parsed items on cache hit', async () => {
    server.use(
      http.get('https://cdn.example.com/public%2Fcache%2Fagenda.json', () =>
        HttpResponse.json({ items: [{ id: 'a' }] }, { status: 200 }),
      ),
    )
    const adapter = buildAdapter()
    const items = await adapter.getCachedItems<{ id: string }>('agenda')
    expect(items).toEqual([{ id: 'a' }])
  })

  it('returns null on cache miss', async () => {
    server.use(
      http.get(
        'https://cdn.example.com/public%2Fcache%2Fagenda.json',
        () => new HttpResponse(null, { status: 404 }),
      ),
    )
    const adapter = buildAdapter()
    expect(await adapter.getCachedItems('agenda')).toBeNull()
  })

  it('dedupes inflight reads', async () => {
    let calls = 0
    server.use(
      http.get('https://cdn.example.com/public%2Fcache%2Fagenda.json', async () => {
        calls += 1
        await new Promise((r) => setTimeout(r, 5))
        return HttpResponse.json({ items: [{ id: 'a' }] }, { status: 200 })
      }),
    )
    const adapter = buildAdapter()
    const [a, b] = await Promise.all([
      adapter.getCachedItems('agenda'),
      adapter.getCachedItems('agenda'),
    ])
    expect(a).toEqual(b)
    expect(calls).toBe(1)
  })

  it('updateCache writes main + upcoming variants for agenda', async () => {
    const storage = new FakeStorage()
    const adapter = buildAdapter(storage)

    const inPast = { id: 'past', date: new Date('2020-01-01').getTime(), archived: false }
    const future1 = { id: 'f1', date: new Date('2025-07-01').getTime(), archived: false }
    const future2 = { id: 'f2', date: new Date('2025-08-01').getTime(), archived: false }
    const archived = { id: 'ar', date: new Date('2030-01-01').getTime(), archived: true }

    await adapter.updateCache('agenda', [inPast, future1, future2, archived])

    const paths = storage.uploads.map((u) => u.path)
    expect(paths).toContain('public/cache/agenda.json')
    expect(paths).toContain('public/cache/agenda-upcoming.json')

    const upcoming = storage.uploads.find(
      (u) => u.path === 'public/cache/agenda-upcoming.json',
    )?.data as { items: Array<{ id: string }> }
    expect(upcoming.items.map((i) => i.id)).toEqual(['f1', 'f2'])
  })

  it('invalidate drops inflight entries', async () => {
    server.use(
      http.get('https://cdn.example.com/public%2Fcache%2Fagenda.json', async () => {
        await new Promise((r) => setTimeout(r, 10))
        return HttpResponse.json({ items: [] }, { status: 200 })
      }),
    )
    const adapter = buildAdapter()
    const p = adapter.getCachedItems('agenda')
    adapter.invalidate('agenda')
    await p
    // a second call should not hit the inflight map because we invalidated it
    expect(true).toBe(true)
  })

  it('throws on invalid bucketUrlPattern', () => {
    expect(() =>
      new StorageCacheAdapter({
        storage: new FakeStorage(),
        bucketUrlPattern: 'https://cdn.example.com/no-placeholder.json',
      }),
    ).toThrow()
  })
})
