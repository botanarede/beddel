/**
 * Known field names that carry timestamp values across the public API.
 *
 * All adapters and server handlers reuse this list when serialising or
 * normalising timestamps, keeping client and server in lockstep.
 */
export const TIMESTAMP_FIELDS = [
  'createdAt',
  'date',
  'updated_at',
  'updatedAt',
  'created_at',
] as const

export type TimestampField = (typeof TIMESTAMP_FIELDS)[number]

/**
 * Convert any supported timestamp representation to a `Date`.
 *
 * @param value — epoch milliseconds, an existing `Date`, or an ISO-8601 string.
 * @returns A `Date` instance, or `null` when the value cannot be parsed.
 */
export function toDate(value: unknown): Date | null {
  if (value === undefined || value === null) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  if (typeof value === 'number') {
    const d = new Date(value)
    return Number.isNaN(d.getTime()) ? null : d
  }
  if (typeof value === 'string') {
    const parsed = Date.parse(value)
    return Number.isNaN(parsed) ? null : new Date(parsed)
  }
  return null
}

/**
 * Convert a `Date` to epoch milliseconds. If `date` is already a number it
 * is returned unchanged.
 */
export function dateToMillis(date: Date | number): number {
  if (typeof date === 'number') return date
  return date.getTime()
}

/** Current epoch milliseconds (wrapped for test injection / mocking). */
export function nowMillis(): number {
  return Date.now()
}

/** Returns midnight (00:00:00.000) for the supplied date in local time. */
export function startOfDayMillis(reference: Date = new Date()): number {
  const d = new Date(reference)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

/**
 * Stable comparator suitable for `Array.prototype.sort`.
 *
 * Uses `toDate` to coerce each value so that mixed inputs (number + Date +
 * ISO string) sort correctly. Unknown or missing values sort last.
 */
export function sortByDate<T extends Record<string, unknown>>(
  a: T,
  b: T,
  field: keyof T = 'date' as keyof T,
  direction: 'asc' | 'desc' = 'asc',
): number {
  const da = toDate(a[field])?.getTime() ?? Number.POSITIVE_INFINITY
  const db = toDate(b[field])?.getTime() ?? Number.POSITIVE_INFINITY
  const delta = da - db
  return direction === 'asc' ? delta : -delta
}
