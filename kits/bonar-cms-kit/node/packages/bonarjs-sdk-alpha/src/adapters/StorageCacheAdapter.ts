import type { ICacheAdapter } from '../core/interfaces/ICacheAdapter'
import type { IStorageAdapter } from '../core/interfaces/IStorageAdapter'
import type { BusinessInfo, CacheVariant, StorageMetadata } from '../core/types'
import { CacheError } from '../core/errors'
import { startOfDayMillis } from '../core/utils/timestamps'

const DEFAULT_PUBLIC_TABLES: readonly string[] = ['agenda', 'metadata']
const DEFAULT_UPCOMING_LIMIT = 20
const DEFAULT_CACHE_METADATA: StorageMetadata = {
  contentType: 'application/json',
  cacheControl: 'public, max-age=300',
}

/** Configuration for {@link StorageCacheAdapter}. */
export interface StorageCacheAdapterConfig {
  /** Storage adapter used to write cache files. */
  storage: IStorageAdapter
  /**
   * URL pattern used to read public cache files from a CDN. Must contain
   * the literal `{file}` placeholder, which is replaced with the file
   * basename (e.g. `agenda`, `agenda-upcoming`).
   */
  bucketUrlPattern: string
  /** Tables whose items should be mirrored to the cache. */
  publicTables?: readonly string[]
  /** Business info used to build JSON-LD schemas for events. */
  business?: BusinessInfo
  /** Prefix for cache object paths. Defaults to `public/cache`. */
  pathPrefix?: string
  /** Maximum items in the `upcoming` variant. Defaults to 20. */
  upcomingLimit?: number
  /** Override the default `fetch` implementation (useful for tests). */
  fetchImpl?: typeof fetch
  /** Clock override, primarily for tests. */
  nowMillisFn?: () => number
}

interface CacheEnvelope<T> {
  table?: string
  variant?: string
  updatedAt?: string
  count?: number
  items?: T[]
}

function buildEventJsonLd(
  item: Record<string, unknown>,
  business: BusinessInfo,
): Record<string, unknown> {
  const dateMs = typeof item.date === 'number' ? item.date : 0
  const d = new Date(dateMs)
  const dateOnly = d.toISOString().split('T')[0]
  const startTime = typeof item.time === 'string' ? item.time : '19:00'
  const title = typeof item.title === 'string' ? item.title : ''
  const description =
    typeof item.description === 'string' && item.description.length > 0
      ? item.description
      : `${title}${business.defaultDescriptionSuffix ?? ''}`
  const image = typeof item.image === 'string' ? item.image : ''
  const link = typeof item.link === 'string' ? item.link : undefined

  const payload: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': 'MusicEvent',
    name: title,
    description,
    startDate: `${dateOnly}T${startTime}:00-03:00`,
    endDate: `${dateOnly}T23:59:00-03:00`,
    image: image.startsWith('http') ? image : `${business.siteUrl}${image}`,
    url: `${business.siteUrl}/agenda`,
    eventStatus: 'https://schema.org/EventScheduled',
    eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
    location: {
      '@type': 'Place',
      '@id': business.id,
      name: business.name,
      ...(business.address && {
        address: {
          '@type': 'PostalAddress',
          ...business.address,
        },
      }),
    },
    organizer: {
      '@type': 'Organization',
      '@id': business.id,
      name: business.name,
      url: business.siteUrl,
    },
    performer: { '@type': 'MusicGroup', name: title },
  }

  if (link) {
    payload.offers = {
      '@type': 'Offer',
      url: link,
      priceCurrency: 'BRL',
      price: '0',
      availability: 'https://schema.org/InStock',
      validFrom: `${dateOnly}T${startTime}:00-03:00`,
    }
  }

  return payload
}

/**
 * Cache adapter that mirrors public-table data to a storage bucket and reads
 * it back via a configurable CDN URL.
 *
 * This is the generic, provider-agnostic replacement for the legacy
 * `PublicDataCacheService` (which was hard-wired to Firebase Storage).
 */
export class StorageCacheAdapter implements ICacheAdapter {
  private readonly storage: IStorageAdapter
  private readonly bucketUrlPattern: string
  private readonly publicTables: Set<string>
  private readonly business?: BusinessInfo
  private readonly pathPrefix: string
  private readonly upcomingLimit: number
  private readonly fetchImpl: typeof fetch
  private readonly nowMillisFn: () => number
  private readonly inflight = new Map<string, Promise<unknown[] | null>>()

  constructor(config: StorageCacheAdapterConfig) {
    if (!config.bucketUrlPattern || !config.bucketUrlPattern.includes('{file}')) {
      throw new CacheError(
        'cache/invalid-config',
        'StorageCacheAdapter requires bucketUrlPattern containing the "{file}" placeholder.',
      )
    }
    this.storage = config.storage
    this.bucketUrlPattern = config.bucketUrlPattern
    this.publicTables = new Set(config.publicTables ?? DEFAULT_PUBLIC_TABLES)
    this.business = config.business
    this.pathPrefix = (config.pathPrefix ?? 'public/cache').replace(/\/+$/, '')
    this.upcomingLimit = config.upcomingLimit ?? DEFAULT_UPCOMING_LIMIT
    this.fetchImpl = config.fetchImpl ?? globalThis.fetch.bind(globalThis)
    this.nowMillisFn = config.nowMillisFn ?? (() => Date.now())
  }

  /** Returns true when `table` is mirrored by this adapter. */
  isPublicTable(table: string): boolean {
    return this.publicTables.has(table)
  }

  private fileName(table: string, variant?: CacheVariant): string {
    return variant ? `${table}-${variant}` : table
  }

  private buildPublicUrl(table: string, variant?: CacheVariant): string {
    const file = this.fileName(table, variant)
    return this.bucketUrlPattern.replace('{file}', file)
  }

  private buildStoragePath(table: string, variant?: CacheVariant): string {
    return `${this.pathPrefix}/${this.fileName(table, variant)}.json`
  }

  async getCachedItems<T = unknown>(
    table: string,
    variant?: CacheVariant,
  ): Promise<T[] | null> {
    if (!this.isPublicTable(table)) return null

    const cacheKey = this.fileName(table, variant)
    const existing = this.inflight.get(cacheKey)
    if (existing) return existing as Promise<T[] | null>

    const promise: Promise<T[] | null> = this.fetchImpl(
      this.buildPublicUrl(table, variant),
    )
      .then(async (res) => {
        if (!res.ok) return null
        try {
          const data = (await res.json()) as CacheEnvelope<T>
          return Array.isArray(data?.items) ? data.items : null
        } catch {
          return null
        }
      })
      .catch(() => null)
      .finally(() => {
        this.inflight.delete(cacheKey)
      })

    this.inflight.set(cacheKey, promise as Promise<unknown[] | null>)
    return promise
  }

  async updateCache(table: string, items: unknown[]): Promise<void> {
    if (!this.isPublicTable(table)) return
    const list = Array.isArray(items) ? items : []
    const now = new Date(this.nowMillisFn()).toISOString()

    try {
      await this.storage.uploadJSON(
        this.buildStoragePath(table),
        { table, updatedAt: now, count: list.length, items: list },
        DEFAULT_CACHE_METADATA,
      )
    } catch (err) {
      throw new CacheError(
        'cache/upload-failed',
        `Failed to upload cache for table "${table}"`,
        { cause: err },
      )
    }

    if (table === 'agenda') {
      const upcoming = this.buildUpcoming(list as Record<string, unknown>[])
      try {
        await this.storage.uploadJSON(
          this.buildStoragePath(table, 'upcoming'),
          {
            table,
            variant: 'upcoming',
            updatedAt: now,
            count: upcoming.length,
            items: upcoming,
          },
          DEFAULT_CACHE_METADATA,
        )

        if (this.business) {
          const schemas = upcoming.map((item) =>
            buildEventJsonLd(item, this.business as BusinessInfo),
          )
          await this.storage.uploadJSON(
            this.buildStoragePath(table, 'schemas'),
            { updatedAt: now, count: schemas.length, schemas },
            DEFAULT_CACHE_METADATA,
          )
        }
      } catch (err) {
        throw new CacheError(
          'cache/upload-variant-failed',
          `Failed to upload cache variant for table "${table}"`,
          { cause: err },
        )
      }
    }
  }

  invalidate(table: string): void {
    for (const key of this.inflight.keys()) {
      if (key === table || key.startsWith(`${table}-`)) {
        this.inflight.delete(key)
      }
    }
  }

  private buildUpcoming(
    items: Record<string, unknown>[],
  ): Record<string, unknown>[] {
    const midnight = startOfDayMillis(new Date(this.nowMillisFn()))
    return items
      .filter((item) => {
        if (item?.archived) return false
        const date = typeof item?.date === 'number' ? item.date : 0
        return date >= midnight
      })
      .sort((a, b) => {
        const da = typeof a.date === 'number' ? a.date : 0
        const db = typeof b.date === 'number' ? b.date : 0
        return da - db
      })
      .slice(0, this.upcomingLimit)
  }
}
