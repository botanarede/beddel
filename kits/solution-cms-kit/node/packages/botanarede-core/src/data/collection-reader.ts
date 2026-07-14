/**
 * Public collection reader — resolves a CollectionQuery to rows.
 *
 * Enforces publicRead guard, applies limit, and supports request-scoped
 * caching to avoid duplicate adapter calls within a single page render.
 */

import type { CollectionQuery } from '@botanarede/schema';
import { assertPublicRead } from '@botanarede/schema';

/** A row returned by the collection adapter. */
export type Row = Record<string, unknown> & { id: string };

/** Adapter interface for fetching collection rows from a data source. */
export interface CollectionDataAdapter {
  fetchRows(tenantId: string, tableSlug: string, query: CollectionQuery): Promise<Row[]>;
}

function cacheKey(tenantId: string, query: CollectionQuery): string {
  return `${tenantId}:${query.tableSlug}:${JSON.stringify(query)}`;
}

/**
 * Resolves a CollectionQuery to an array of Row objects.
 *
 * - Throws QueryNotPublicError if publicRead is false.
 * - Uses request-scoped cache to deduplicate adapter calls.
 * - Applies limit after adapter returns.
 * - On adapter error, returns [] (graceful degradation).
 */
export async function resolveCollectionQuery(
  query: CollectionQuery,
  tenantId: string,
  adapter: CollectionDataAdapter,
  cache?: Map<string, Row[]>,
): Promise<Row[]> {
  assertPublicRead(query);

  const key = cacheKey(tenantId, query);

  if (cache?.has(key)) {
    return cache.get(key)!;
  }

  let rows: Row[];
  try {
    rows = await adapter.fetchRows(tenantId, query.tableSlug, query);
  } catch {
    return [];
  }

  if (query.limit != null && rows.length > query.limit) {
    rows = rows.slice(0, query.limit);
  }

  cache?.set(key, rows);
  return rows;
}
