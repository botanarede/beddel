import type { Timestamp } from 'firebase-admin/firestore'

import {
  TIMESTAMP_FIELDS,
  type TimestampField,
} from '../../core/utils/timestamps'

/** Minimal Firestore Timestamp factory. */
export interface TimestampFactory {
  fromMillis(ms: number): Timestamp
}

/**
 * Convert every known-timestamp field in `data` (currently a `number` in
 * epoch ms) to a Firestore `Timestamp` via `factory.fromMillis`.
 *
 * `factory` is injected so this module does not depend on `firebase-admin`
 * at module-load time. Consumers typically pass the static `Timestamp` class.
 */
export function normalizeTimestamps(
  data: Record<string, unknown>,
  factory: TimestampFactory,
): Record<string, unknown> {
  const result: Record<string, unknown> = { ...data }
  for (const field of TIMESTAMP_FIELDS as readonly TimestampField[]) {
    const value = result[field]
    if (typeof value === 'number') {
      result[field] = factory.fromMillis(value)
    }
  }
  return result
}

export { TIMESTAMP_FIELDS }
