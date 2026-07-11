import { describe, expect, it, vi } from 'vitest'

import { RefreshCache } from '../../../src/core/useCases/cache/RefreshCache'
import { CacheError } from '../../../src/core/errors'
import type { IDatabaseAdapter } from '../../../src/core/interfaces/IDatabaseAdapter'
import { FakeCache, FakeDatabase } from '../../fixtures/fakeAdapters'

describe('useCases/RefreshCache', () => {
  it('happy path: single attempt, cache populated', async () => {
    const db = new FakeDatabase({ seed: { agenda: [{ id: 'a' }] } })
    const cache = new FakeCache()
    await new RefreshCache(db, cache).execute('agenda')
    expect(cache.writes).toHaveLength(1)
    expect(cache.writes[0]?.items).toHaveLength(1)
  })

  it('retries once on failure before succeeding', async () => {
    vi.useFakeTimers()
    const cache = new FakeCache()
    let attempts = 0
    const flakyDb: IDatabaseAdapter = {
      async getItems<T>(): Promise<T[]> {
        attempts += 1
        if (attempts === 1) throw new Error('boom')
        return [{ id: 'x' } as unknown as T]
      },
      async getItemById<T>(): Promise<T | null> {
        return null
      },
      async setItem<T>(): Promise<T> {
        return null as unknown as T
      },
      async deleteItemById() {
        return { success: true as const }
      },
      async getItemChildById<T>(): Promise<T | null> {
        return null
      },
    }

    const p = new RefreshCache(flakyDb, cache).execute('agenda')
    await vi.advanceTimersByTimeAsync(1000)
    await p
    expect(attempts).toBe(2)
    expect(cache.writes).toHaveLength(1)
    vi.useRealTimers()
  })

  it('throws CacheError after MAX_ATTEMPTS failures', async () => {
    vi.useFakeTimers()
    const cache = new FakeCache()
    const brokenDb: IDatabaseAdapter = {
      async getItems<T>(): Promise<T[]> {
        throw new Error('down')
      },
      async getItemById<T>(): Promise<T | null> {
        return null
      },
      async setItem<T>(): Promise<T> {
        return null as unknown as T
      },
      async deleteItemById() {
        return { success: true as const }
      },
      async getItemChildById<T>(): Promise<T | null> {
        return null
      },
    }

    const p = new RefreshCache(brokenDb, cache)
      .execute('agenda')
      .catch((e) => e)
    await vi.advanceTimersByTimeAsync(1000)
    const err = await p
    expect(err).toBeInstanceOf(CacheError)
    vi.useRealTimers()
  })
})
