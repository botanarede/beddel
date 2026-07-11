/**
 * Data Binding Resolver — fetches data at build time for sections
 * that declare a `dataBinding` in their tenant JSON config.
 *
 * Reads from the Firebase Storage public cache (pre-cached JSON files).
 * Cache URL pattern is configurable via NEXT_PUBLIC_CACHE_URL_PATTERN env var.
 * Errors are logged but do not crash the build — sections render with
 * empty data arrays.
 */

import type { Section, DataBinding } from '@botanarede/schema'
import { assertPublicRead } from '@botanarede/schema'
import { marked } from 'marked'

const STORAGE_BUCKET = process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET ?? ''
const TENANT_ID = process.env.EXPORT_TENANT_ID ?? 'brasilprana'

/**
 * Default Firebase Storage URL pattern.
 * Placeholders: {bucket}, {path}
 * The {path} is constructed as {tenantId}/{tableSlug}.json for collections/documents,
 * or {tenantId}/{contentPath} for content bindings.
 */
const DEFAULT_CACHE_URL_PATTERN =
  'https://firebasestorage.googleapis.com/v0/b/{bucket}/o/public%2Fcache%2F{path}?alt=media'

const CACHE_URL_PATTERN = process.env.NEXT_PUBLIC_CACHE_URL_PATTERN ?? DEFAULT_CACHE_URL_PATTERN

export interface ResolvedSection extends Omit<Section, 'dataBinding'> {
  dataBinding?: DataBinding
  resolvedData?: unknown[]
}

/**
 * For Firebase Storage, paths need URL encoding with %2F for slashes.
 */
function buildFirebaseStorageCacheUrl(relativePath: string): string {
  const fullPath = `${TENANT_ID}/${relativePath}`
  // Firebase Storage uses %2F for path separators in the object name
  const encodedPath = fullPath.split('/').join('%2F')
  return CACHE_URL_PATTERN
    .replace('{bucket}', STORAGE_BUCKET)
    .replace('{path}', encodedPath)
}

async function fetchCachedData(binding: DataBinding, tenantId: string): Promise<unknown[]> {
  // Check publicRead for all binding types
  if (!binding.publicRead) {
    console.error(`[resolve-data] Binding is not marked as publicRead`)
    return []
  }

  if (binding.type === 'content') {
    const url = buildFirebaseStorageCacheUrl(binding.path)
    try {
      const res = await fetch(url)
      if (!res.ok) {
        console.warn(`[resolve-data] Content fetch failed (${res.status}): ${binding.path}`)
        return []
      }
      const rawMarkdown = await res.text()
      const html = await marked(rawMarkdown)
      return [{ html, rawMarkdown }]
    } catch (err) {
      console.error(`[resolve-data] Failed to fetch content ${binding.path}:`, err)
      return []
    }
  }

  if (binding.type === 'collection') {
    assertPublicRead(binding)
    const url = buildFirebaseStorageCacheUrl(`${binding.tableSlug}.json`)
    try {
      const res = await fetch(url)
      if (!res.ok) return []
      const json = (await res.json()) as { items?: unknown[] }
      let items: Record<string, unknown>[] = (json?.items ?? []) as Record<string, unknown>[]

      // Client-side filtering
      if (binding.filters) {
        for (const filter of binding.filters) {
          items = items.filter((item) => {
            const val = item[filter.field]
            switch (filter.op) {
              case 'eq': return val === filter.value
              case 'neq': return val !== filter.value
              case 'gt': return (val as number) > (filter.value as number)
              case 'lt': return (val as number) < (filter.value as number)
              case 'gte': return (val as number) >= (filter.value as number)
              case 'lte': return (val as number) <= (filter.value as number)
              default: return true
            }
          })
        }
      }

      // Ordering
      if (binding.orderBy) {
        const { field, direction } = binding.orderBy
        items.sort((a, b) => {
          const aVal = (a[field] as number) ?? 0
          const bVal = (b[field] as number) ?? 0
          return direction === 'asc' ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1)
        })
      }

      // Limit
      if (binding.limit) {
        items = items.slice(0, binding.limit)
      }

      return items
    } catch (err) {
      console.error(`[resolve-data] Failed to fetch ${binding.tableSlug}:`, err)
      return []
    }
  }

  if (binding.type === 'document') {
    assertPublicRead(binding)
    const url = buildFirebaseStorageCacheUrl(`${binding.tableSlug}.json`)
    try {
      const res = await fetch(url)
      if (!res.ok) return []
      const json = (await res.json()) as { items?: Record<string, unknown>[] }
      const items = json?.items ?? []
      const doc = items.find((item) => item['id'] === binding.documentId)
      return doc ? [doc] : []
    } catch (err) {
      console.error(`[resolve-data] Failed to fetch doc ${binding.documentId}:`, err)
      return []
    }
  }

  return []
}

export async function resolveDataBindings(
  sections: Section[],
  tenantId: string,
): Promise<ResolvedSection[]> {
  return Promise.all(
    sections.map(async (section): Promise<ResolvedSection> => {
      if (!section.dataBinding) {
        return section as ResolvedSection
      }

      const resolvedData = await fetchCachedData(
        section.dataBinding as DataBinding,
        tenantId,
      )
      return { ...section, resolvedData }
    }),
  )
}
