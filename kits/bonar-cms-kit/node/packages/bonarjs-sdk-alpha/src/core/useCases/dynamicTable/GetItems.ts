import type { IDatabaseAdapter } from '../../interfaces/IDatabaseAdapter'
import type { QueryOptions } from '../../types'

/**
 * Read a full list of items from a table, filtering out archived ones.
 *
 * Archived filtering is performed client-side so every caller gets the same
 * "active items" semantics regardless of the backing store.
 */
export class GetItems {
  constructor(private readonly database: IDatabaseAdapter) {}

  async execute<T extends { archived?: boolean } = Record<string, unknown>>(
    table: string,
    options?: QueryOptions,
  ): Promise<T[]> {
    const items = await this.database.getItems<T>(table, options)
    if (!Array.isArray(items) || items.length === 0) return []
    return items.filter((item) => !item?.archived)
  }
}
