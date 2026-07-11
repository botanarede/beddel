import type { Firestore, Timestamp } from 'firebase-admin/firestore'

import type {
  AppCheckVerifier,
  AuthVerifier,
} from '../middleware/authGuard'
import type { TimestampFactory } from '../utils/normalizeTimestamps'

/**
 * Shared dependencies required by the route-handler factories in this
 * package. Kept minimal so consumers can wire them from their own
 * `firebase-admin` bootstrap.
 */
export interface HandlerDeps {
  db: Firestore
  appCheck: AppCheckVerifier
  auth: AuthVerifier
  timestampFactory?: TimestampFactory
  publicSubmitTables?: readonly string[]
  /** Optional override, primarily for tests. */
  now?: () => Date
}

/** Static `Timestamp` class used as the default timestamp factory. */
export type FirestoreTimestamp = typeof Timestamp
