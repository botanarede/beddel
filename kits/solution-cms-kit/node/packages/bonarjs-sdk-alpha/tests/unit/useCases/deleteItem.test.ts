import { describe, expect, it, vi } from 'vitest'

import { DeleteItemById } from '../../../src/core/useCases/dynamicTable/DeleteItemById'
import { FakeCache, FakeDatabase } from '../../fixtures/fakeAdapters'

describe('useCases/DeleteItemById', () => {
  it('removes the item and refreshes cache', async () => {
    vi.useFakeTimers()
    const db = new FakeDatabase({
      seed: { agenda: [{ id: 'a' }, { id: 'b' }] },
    })
    const cache = new FakeCache()

    const res = await new DeleteItemById(db, cache).execute('agenda', 'a')
    expect(res).toEqual({ success: true })
    expect(db.tables.agenda).toHaveLength(1)
    expect(cache.invalidations).toContain('agenda')

    await vi.runAllTimersAsync()
    vi.useRealTimers()

    expect(cache.writes.length).toBeGreaterThan(0)
  })

  it('works without a cache adapter', async () => {
    const db = new FakeDatabase({ seed: { agenda: [{ id: 'a' }] } })
    await expect(new DeleteItemById(db).execute('agenda', 'a')).resolves.toEqual({
      success: true,
    })
  })
})
