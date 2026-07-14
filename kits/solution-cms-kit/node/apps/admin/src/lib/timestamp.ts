/**
 * Centralized timestamp utilities.
 *
 * Every timestamp in the public API is epoch milliseconds (number).
 */

/** Convert an epoch-ms number to a Date. Returns null for invalid input. */
export function toDate(value: unknown): Date | null {
  if (value == null) return null
  if (typeof value !== 'number') return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Current time as epoch ms. */
export function nowMillis(): number {
  return Date.now()
}

/** Date or epoch-ms number to epoch ms. */
export function dateToMillis(date: Date | number): number {
  return typeof date === 'number' ? date : date.getTime()
}
