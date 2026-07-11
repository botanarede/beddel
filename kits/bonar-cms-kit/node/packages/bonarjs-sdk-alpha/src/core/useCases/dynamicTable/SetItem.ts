import type { IDatabaseAdapter } from '../../interfaces/IDatabaseAdapter'
import type { ICacheAdapter } from '../../interfaces/ICacheAdapter'
import type { EventType } from '../../types'
import { RefreshCache } from '../cache/RefreshCache'

/**
 * Create or update an item, then refresh the public cache (fire-and-forget).
 *
 * When a cache adapter is supplied, the use case invalidates any inflight
 * cache reads for the table and triggers a fresh cache rebuild. Cache
 * failures are swallowed so the write result is always returned.
 */
export class SetItem {
  constructor(
    private readonly database: IDatabaseAdapter,
    private readonly cache?: ICacheAdapter,
  ) {}

  async execute<T = unknown>(
    table: string,
    data: object,
    id?: string,
    events?: EventType,
  ): Promise<T> {
    const result = await this.database.setItem<T>(table, data, id, events)

    if (this.cache) {
      this.cache.invalidate(table)
      const cache = this.cache
      void new RefreshCache(this.database, cache)
        .execute(table)
        .catch(() => {
          /* fire-and-forget — cache errors must not surface to the caller */
        })
    }

    return result
  }
}
