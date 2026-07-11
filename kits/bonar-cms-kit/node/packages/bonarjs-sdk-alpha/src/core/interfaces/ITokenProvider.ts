/**
 * Pair of token accessors used by HTTP adapters to populate the
 * `X-Firebase-AppCheck` and `X-Firebase-IdToken` headers.
 *
 * Implementations may be async — e.g. the Firebase token provider refreshes
 * App Check tokens on demand.
 */
export interface ITokenProvider {
  /** Fresh App Check token. */
  getAppCheckToken(): Promise<string>

  /** Fresh ID token for the current user; returns `null` when anonymous. */
  getIdToken(): Promise<string | null>
}
