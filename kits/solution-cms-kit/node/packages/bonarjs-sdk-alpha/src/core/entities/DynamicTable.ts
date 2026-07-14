import { z } from 'zod'

/**
 * Zod schema for a dynamic table descriptor.
 *
 * A dynamic table is a named collection of arbitrary JSON documents that
 * lives under `tables/{customerId}/{tableName}` in the upstream database.
 * The schema is intentionally permissive for items: each app defines its own
 * item shape and validates it at the use-case level.
 */
export const DynamicTableSchema = z.object({
  id: z.string().optional(),
  name: z.string().optional(),
  items: z.array(z.unknown()).optional(),
})

export type DynamicTable = z.infer<typeof DynamicTableSchema>
