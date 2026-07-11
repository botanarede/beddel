import type { IDatabaseAdapter } from '../../interfaces/IDatabaseAdapter'
import type { ICacheAdapter } from '../../interfaces/ICacheAdapter'
import { RefreshCache } from '../cache/RefreshCache'

/**
 * Archive-and-delete an item, then refresh the public cache (fire-and-forget).
 */
export class DeleteItemById {
  constructor(
    private readonly database: IDatabaseAdapter,
    private readonly cache?: ICacheAdapter,
  ) {}

  async execute(table: string, id: string): Promise<{ success: true }> {
    const result = await this.database.deleteItemById(table, id)

    if (this.cache) {
      this.cache.invalidate(table)
      const cache = this.cache
      void new RefreshCache(this.database, cache)
        .execute(table)
        .catch(() => {
          /* fire-and-forget */
        })
    }

    return result
  }
}
