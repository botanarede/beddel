import { TIMESTAMP_FIELDS } from '../../core/utils/timestamps'

/** Anything with a `.toMillis()` method, like a Firestore Timestamp. */
interface MillisConvertible {
  toMillis(): number
}

function isMillisConvertible(value: unknown): value is MillisConvertible {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as { toMillis?: unknown }).toMillis === 'function'
  )
}

/**
 * Convert every known-timestamp field in `data` (plus any `.toMillis()`-able
 * object) to epoch milliseconds. Safe to call on `undefined` — returns `{}`.
 */
export function serializeTimestamps(
  data: Record<string, unknown> | undefined,
): Record<string, unknown> {
  if (!data) return {}
  const result: Record<string, unknown> = { ...data }
  for (const [key, value] of Object.entries(result)) {
    if (isMillisConvertible(value)) {
      result[key] = value.toMillis()
    }
  }
  return result
}

export { TIMESTAMP_FIELDS }
