import type { IDatabaseAdapter } from '../core/interfaces/IDatabaseAdapter'
import type { ITokenProvider } from '../core/interfaces/ITokenProvider'
import type { EventType, QueryOptions } from '../core/types'
import { DatabaseError } from '../core/errors'
import { TIMESTAMP_FIELDS, type TimestampField } from '../core/utils/timestamps'

/** Configuration for {@link HttpDatabaseAdapter}. */
export interface HttpDatabaseAdapterConfig {
  /** Base URL of the `bonar-cms-api` service, without trailing slash. */
  apiUrl: string
  /** Customer id / API key, forwarded as the `Authorization` header. */
  apiKey: string
  /** Optional token provider for App Check + ID Token headers. */
  tokenProvider?: ITokenProvider
  /** Override the default `fetch` implementation (useful for tests). */
  fetchImpl?: typeof fetch
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * Walks `data` and normalises every known timestamp field from epoch ms
 * to itself — kept as a pass-through on the client side so the wire
 * contract matches the server handler.
 *
 * The function is defensive: arbitrary provider-specific date shapes (Date
 * instances, ISO strings) are converted to epoch ms so the server-side
 * normalizer can do its job.
 */
function normalizeTimestampsForWire(
  data: Record<string, unknown>,
): Record<string, unknown> {
  const result: Record<string, unknown> = { ...data }
  for (const field of TIMESTAMP_FIELDS as readonly TimestampField[]) {
    const value = result[field]
    if (value instanceof Date) {
      result[field] = value.getTime()
    } else if (typeof value === 'string') {
      const parsed = Date.parse(value)
      if (!Number.isNaN(parsed)) result[field] = parsed
    }
  }
  return result
}

/**
 * HTTP adapter that speaks the `bonar-cms-api` protocol over `fetch`.
 *
 * Implements {@link IDatabaseAdapter}. No Firebase imports.
 */
export class HttpDatabaseAdapter implements IDatabaseAdapter {
  private readonly apiUrl: string
  private readonly apiKey: string
  private readonly tokenProvider?: ITokenProvider
  private readonly fetchImpl: typeof fetch

  constructor(config: HttpDatabaseAdapterConfig) {
    if (!config.apiUrl) {
      throw new DatabaseError(
        'database/invalid-config',
        'HttpDatabaseAdapter requires a non-empty apiUrl.',
      )
    }
    this.apiUrl = config.apiUrl.replace(/\/+$/, '')
    this.apiKey = config.apiKey
    this.tokenProvider = config.tokenProvider
    this.fetchImpl = config.fetchImpl ?? globalThis.fetch.bind(globalThis)
  }

  private async buildHeaders(): Promise<Record<string, string>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Authorization: this.apiKey,
    }
    if (this.tokenProvider) {
      try {
        const appCheck = await this.tokenProvider.getAppCheckToken()
        if (appCheck) headers['X-Firebase-AppCheck'] = appCheck
      } catch {
        /* the API will reject if App Check is required */
      }
      try {
        const idToken = await this.tokenProvider.getIdToken()
        if (idToken) headers['X-Firebase-IdToken'] = idToken
      } catch {
        /* id token is only required for protected writes */
      }
    }
    return headers
  }

  private async request<T>(
    endpoint: string,
    body: Record<string, unknown>,
  ): Promise<T> {
    const headers = await this.buildHeaders()

    let response: Response
    try {
      response = await this.fetchImpl(`${this.apiUrl}${endpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        mode: 'cors',
      })
    } catch (err) {
      throw new DatabaseError(
        'database/network-error',
        `Network error while calling ${endpoint}`,
        { cause: err },
      )
    }

    if (!response.ok) {
      let message = `API request failed: ${response.status} ${response.statusText}`
      try {
        const text = await response.text()
        if (text) message = `${message} — ${text}`
      } catch {
        /* ignore */
      }
      throw new DatabaseError('database/http-error', message, {
        status: response.status,
      })
    }

    try {
      return (await response.json()) as T
    } catch (err) {
      throw new DatabaseError(
        'database/invalid-response',
        `Failed to parse JSON response from ${endpoint}`,
        { cause: err },
      )
    }
  }

  async getItems<T = unknown>(
    table: string,
    options?: QueryOptions,
  ): Promise<T[]> {
    const body: Record<string, unknown> = { table }
    if (options?.where || options?.orderBy || options?.limit) {
      body.queryOptions = {
        where: options?.where,
        orderBy: options?.orderBy,
        limit: options?.limit,
      }
    }
    const data = await this.request<{ content?: T[] | Record<string, never> }>(
      '/api/tables/getItems',
      body,
    )
    if (!data.content || (isPlainObject(data.content) && Object.keys(data.content).length === 0)) {
      return []
    }
    return data.content as T[]
  }

  async getItemById<T = unknown>(
    table: string,
    id: string,
  ): Promise<T | null> {
    const data = await this.request<{ content?: T | null }>(
      '/api/tables/getItemById',
      { table, item_id: id },
    )
    return data.content ?? null
  }

  async setItem<T = unknown>(
    table: string,
    data: object,
    id?: string,
    events?: EventType,
  ): Promise<T> {
    const normalized = isPlainObject(data)
      ? normalizeTimestampsForWire(data)
      : (data as Record<string, unknown>)

    const response = await this.request<{
      item?: T
      content?: T
      message?: string
    }>('/api/tables/setItem', {
      table,
      id,
      data: normalized,
      events: events ?? 'NONE',
    })

    if (response.item !== undefined) return response.item
    if (response.content !== undefined) return response.content
    return response as unknown as T
  }

  async deleteItemById(
    table: string,
    id: string,
  ): Promise<{ success: true }> {
    await this.request<{ success: boolean }>('/api/tables/deleteItemById', {
      table,
      id,
    })
    return { success: true }
  }

  async getItemChildById<T = unknown>(
    table: string,
    itemId: string,
    childName: string,
    childId: string,
  ): Promise<T | null> {
    const data = await this.request<{ content?: T | null }>(
      '/api/tables/getItemChildById',
      { table, item_id: itemId, childName, childId },
    )
    return data.content ?? null
  }
}
