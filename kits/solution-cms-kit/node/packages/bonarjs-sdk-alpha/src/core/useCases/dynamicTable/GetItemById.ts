import type { IDatabaseAdapter } from '../../interfaces/IDatabaseAdapter'

/** Read a single item by id. Returns `null` when the item does not exist. */
export class GetItemById {
  constructor(private readonly database: IDatabaseAdapter) {}

  async execute<T = unknown>(table: string, id: string): Promise<T | null> {
    return this.database.getItemById<T>(table, id)
  }
}
