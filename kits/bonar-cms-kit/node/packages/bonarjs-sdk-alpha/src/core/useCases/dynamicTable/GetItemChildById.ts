import type { IDatabaseAdapter } from '../../interfaces/IDatabaseAdapter'

/** Read a nested child document of an item (e.g. `attendees`). */
export class GetItemChildById {
  constructor(private readonly database: IDatabaseAdapter) {}

  async execute<T = unknown>(
    table: string,
    itemId: string,
    childName: string,
    childId: string,
  ): Promise<T | null> {
    return this.database.getItemChildById<T>(table, itemId, childName, childId)
  }
}
