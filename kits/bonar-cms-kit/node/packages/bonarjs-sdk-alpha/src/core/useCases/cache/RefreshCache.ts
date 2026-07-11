import type { IDatabaseAdapter } from '../../interfaces/IDatabaseAdapter'
import type { ICacheAdapter } from '../../interfaces/ICacheAdapter'
import { CacheError } from '../../errors'

const MAX_ATTEMPTS = 2
const RETRY_DELAY_MS = 1000

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Re-fetches the full table from the database and writes it through the
 * cache adapter. Retries once after a 1s delay before giving up.
 */
export class RefreshCache {
  constructor(
    private readonly database: IDatabaseAdapter,
    private readonly cache: ICacheAdapter,
  ) {}

  async execute(table: string): Promise<void> {
    let lastError: unknown

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
      try {
        const items = await this.database.getItems<Record<string, unknown>>(table)
        await this.cache.updateCache(table, items ?? [])
        return
      } catch (err) {
        lastError = err
        if (attempt < MAX_ATTEMPTS) {
          await sleep(RETRY_DELAY_MS)
        }
      }
    }

    throw new CacheError(
      'cache/refresh-failed',
      `Failed to refresh cache for table "${table}" after ${MAX_ATTEMPTS} attempts.`,
      { cause: lastError },
    )
  }
}
