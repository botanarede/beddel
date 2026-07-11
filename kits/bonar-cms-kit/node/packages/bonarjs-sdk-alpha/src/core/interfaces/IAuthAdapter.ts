import type { User } from '../entities/User'
import type {
  LoginResult,
  OAuthProvider,
  OAuthSignInOptions,
} from '../types'

/**
 * Auth capability required by the SDK, expressed independently of any
 * concrete provider.
 *
 * Provider implementations live in `src/providers/*`. The HTTP adapter for
 * this interface lives in `src/adapters/HttpAuthAdapter.ts`.
 */
export interface IAuthAdapter {
  /** Sign in with an email/password pair. */
  signInWithEmailPassword(email: string, password: string): Promise<LoginResult>

  /**
   * Sign in with an email code.
   *
   * - Called without `code`: issues the code (returns `LoginStatus.EMAIL_SENT`).
   * - Called with `code`: validates the code and completes the sign-in
   *   (returns `LoginStatus.SUCCESS` on success).
   */
  signInWithEmailCode(email: string, code?: number): Promise<LoginResult>

  /** Sign in via an OAuth provider. */
  signInWithOAuth(
    provider: OAuthProvider,
    options?: OAuthSignInOptions,
  ): Promise<LoginResult>

  /** Sign the current user out; idempotent when already signed out. */
  signOut(): Promise<void>

  /** Return the currently signed-in user, or `null` when anonymous. */
  getCurrentUser(): Promise<User | null>

  /**
   * Subscribe to auth state changes. Returns an `unsubscribe` function the
   * caller must invoke when the listener is no longer needed.
   */
  onAuthStateChanged(listener: (user: User | null) => void): () => void

  /** Return a fresh ID token for the current user (if signed in). */
  getIdToken(): Promise<string | null>
}
