/**
 * Metadata document binding — resolves a DocumentQuery to a single record.
 *
 * Enforces publicRead guard and supports request-scoped caching.
 * Returns null when the document does not exist (not an error).
 */

import type { DocumentQuery } from '@botanarede/schema';
import { assertPublicRead } from '@botanarede/schema';

/** Adapter interface for fetching a single document from a data source. */
export interface DocumentDataAdapter {
  fetchDocument(
    tenantId: string,
    tableSlug: string,
    documentId: string,
  ): Promise<Record<string, unknown> | null>;
}

function cacheKey(tenantId: string, query: DocumentQuery): string {
  return `${tenantId}:${query.tableSlug}:${query.documentId}`;
}

/**
 * Resolves a DocumentQuery to a single record or null.
 *
 * - Throws QueryNotPublicError if publicRead is false.
 * - Uses request-scoped cache (caches null too).
 * - Returns null when document does not exist.
 */
export async function resolveDocumentQuery(
  query: DocumentQuery,
  tenantId: string,
  adapter: DocumentDataAdapter,
  cache?: Map<string, Record<string, unknown> | null>,
): Promise<Record<string, unknown> | null> {
  assertPublicRead(query);

  const key = cacheKey(tenantId, query);

  if (cache?.has(key)) {
    return cache.get(key) ?? null;
  }

  const result = await adapter.fetchDocument(tenantId, query.tableSlug, query.documentId);

  cache?.set(key, result);
  return result;
}
