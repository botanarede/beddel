/**
 * Declarative query/binding contract for data-bound components.
 *
 * Defines Zod schemas for CollectionQuery, DocumentQuery, and their
 * discriminated union DataBinding. Components declare data needs in
 * their config JSON; the runtime resolves them at render time.
 *
 * No runtime implementation here — resolvers live in botanarede-runtime
 * (Stories 5.2 and 5.3).
 */

import { z } from 'zod';

// --- Filter and ordering primitives ---

export const FilterClauseSchema = z
  .object({
    field: z.string(),
    op: z.enum(['eq', 'neq', 'gt', 'lt', 'gte', 'lte', 'in']),
    value: z.unknown(),
  })
  .strict();

export type FilterClause = z.infer<typeof FilterClauseSchema>;

export const OrderClauseSchema = z
  .object({
    field: z.string(),
    direction: z.enum(['asc', 'desc']),
  })
  .strict();

export type OrderClause = z.infer<typeof OrderClauseSchema>;

// --- Query schemas ---

export const CollectionQuerySchema = z
  .object({
    type: z.literal('collection'),
    tableSlug: z.string().min(1),
    filters: z.array(FilterClauseSchema).optional(),
    orderBy: OrderClauseSchema.optional(),
    limit: z.number().int().positive().optional(),
    publicRead: z.boolean(),
  })
  .strict();

export type CollectionQuery = z.infer<typeof CollectionQuerySchema>;

export const DocumentQuerySchema = z
  .object({
    type: z.literal('document'),
    tableSlug: z.string().min(1),
    documentId: z.string().min(1),
    publicRead: z.boolean(),
  })
  .strict();

export type DocumentQuery = z.infer<typeof DocumentQuerySchema>;

export const ContentBindingSchema = z
  .object({
    type: z.literal('content'),
    path: z.string().min(1),
    publicRead: z.boolean(),
  })
  .strict();

export type ContentBinding = z.infer<typeof ContentBindingSchema>;

// --- Discriminated union ---

export const DataBindingSchema = z.discriminatedUnion('type', [
  CollectionQuerySchema,
  DocumentQuerySchema,
  ContentBindingSchema,
]);

export type DataBinding = z.infer<typeof DataBindingSchema>;

// --- Error class ---

/**
 * Thrown when a query with `publicRead: false` is resolved on the public site.
 * Defined here in schema; thrown by resolvers in botanarede-runtime.
 */
export class QueryNotPublicError extends Error {
  constructor(tableSlug: string) {
    super(`Query on table "${tableSlug}" is not marked as publicRead`);
    this.name = 'QueryNotPublicError';
  }
}

/**
 * Guard: throws QueryNotPublicError if the query is not public.
 * Used by runtime resolvers before executing a query.
 */
export function assertPublicRead(query: DataBinding): void {
  if (!query.publicRead) {
    const identifier = 'tableSlug' in query ? query.tableSlug : ('path' in query ? query.path : 'unknown')
    throw new QueryNotPublicError(identifier);
  }
}
