import type { EventType, QueryOptions } from '../types'

/**
 * CRUD capability required by the SDK.
 *
 * The canonical implementation is `HttpDatabaseAdapter` which speaks the
 * `bonar-cms-api` HTTP protocol. Provider-native implementations (e.g.
 * direct Firestore) can be supplied instead.
 */
export interface IDatabaseAdapter {
  /**
   * List items from a table, optionally filtered by `QueryOptions`.
   *
   * Returns `[]` when the table is empty. Never returns `null`.
   */
  getItems<T = unknown>(table: string, options?: QueryOptions): Promise<T[]>

  /** Read a single item by id. Returns `null` when the item does not exist. */
  getItemById<T = unknown>(table: string, id: string): Promise<T | null>

  /**
   * Create or update an item.
   *
   * - When `id` is `undefined`, the adapter performs an insert.
   * - When `id` is supplied, the adapter performs an upsert-by-id.
   * - `events` is an optional side-effect hint (`'EMAIL' | 'TICKET' | 'NONE'`).
   */
  setItem<T = unknown>(
    table: string,
    data: object,
    id?: string,
    events?: EventType,
  ): Promise<T>

  /**
   * Archive-and-delete an item. Returns `{ success: true }` on success.
   *
   * Resolves to a soft-delete: the underlying implementation is expected to
   * copy the item to an `archived` collection before deleting.
   */
  deleteItemById(table: string, id: string): Promise<{ success: true }>

  /**
   * Read a nested child document — e.g. an `attendees` sub-collection
   * of an `events` item. Returns `null` when the child does not exist.
   */
  getItemChildById<T = unknown>(
    table: string,
    itemId: string,
    childName: string,
    childId: string,
  ): Promise<T | null>
}
