import { describe, expect, it, vi } from 'vitest'

import { SetItem } from '../../../src/core/useCases/dynamicTable/SetItem'
import { FakeCache, FakeDatabase } from '../../fixtures/fakeAdapters'

describe('useCases/SetItem', () => {
  it('writes through the database', async () => {
    const db = new FakeDatabase()
    const result = await new SetItem(db).execute<{ id: string }>(
      'agenda',
      { title: 'X' },
    )
    expect(result.id).toBeDefined()
    expect(db.calls.setItem).toHaveLength(1)
  })

  it('invalidates and refreshes the cache when provided', async () => {
    vi.useFakeTimers()
    const db = new FakeDatabase({ seed: { agenda: [{ id: 'z' }] } })
    const cache = new FakeCache()

    await new SetItem(db, cache).execute('agenda', { title: 'X' })
    expect(cache.invalidations).toContain('agenda')

    // flush pending microtasks + the fire-and-forget cache refresh
    await vi.runAllTimersAsync()
    vi.useRealTimers()

    expect(cache.writes.length).toBeGreaterThan(0)
    expect(cache.writes[0]?.table).toBe('agenda')
  })
})
