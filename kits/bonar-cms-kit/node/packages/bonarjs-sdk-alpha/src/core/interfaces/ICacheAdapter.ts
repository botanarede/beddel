import type { CacheVariant } from '../types'

/**
 * Read-through / write-through cache over public table data.
 *
 * The reference implementation (`StorageCacheAdapter`) stores variants as
 * individual JSON files in an `IStorageAdapter` and reads them back via a
 * configurable public CDN URL pattern.
 */
export interface ICacheAdapter {
  /**
   * Read the cached items for `table`, optionally selecting a variant (e.g.
   * `'upcoming'`). Returns `null` on cache miss or network error.
   */
  getCachedItems<T = unknown>(
    table: string,
    variant?: CacheVariant,
  ): Promise<T[] | null>

  /**
   * Refresh the cache entry for `table` using `items` as the source of truth.
   * Implementations may also derive additional variants (e.g. `upcoming`,
   * `schemas`) synchronously.
   */
  updateCache(table: string, items: unknown[]): Promise<void>

  /**
   * Invalidate any inflight / in-memory state for `table` so the next read
   * hits the origin. Does not necessarily delete the persisted cache file.
   */
  invalidate(table: string): void
}
