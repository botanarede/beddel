import {
  GoogleAuthProvider,
  onAuthStateChanged as firebaseOnAuthStateChanged,
  signInWithCustomToken,
  signInWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
  signOut as firebaseSignOut,
  type Auth,
  type User as FirebaseUser,
} from 'firebase/auth'

import type { IAuthAdapter } from '../../core/interfaces/IAuthAdapter'
import type { User } from '../../core/entities/User'
import type {
  LoginResult,
  OAuthProvider,
  OAuthSignInOptions,
} from '../../core/types'
import { LoginStatus } from '../../core/types'
import { AuthError } from '../../core/errors'
import type { HttpAuthAdapter } from '../../adapters/HttpAuthAdapter'

/** Configuration for {@link FirebaseAuthAdapter}. */
export interface FirebaseAuthAdapterConfig {
  auth: Auth
  /**
   * When provided, the adapter delegates email-code flows (and custom-token
   * exchange) to the HTTP adapter — this matches the legacy split between
   * `AuthRepository` and `bonar-cms-api`.
   */
  httpAuth?: HttpAuthAdapter
}

function toUser(fb: FirebaseUser | null): User | null {
  if (!fb || !fb.email) return null
  return {
    id: fb.uid,
    email: fb.email,
    name: fb.displayName ?? undefined,
  }
}

/** IAuthAdapter implementation that uses the Firebase client SDK. */
export class FirebaseAuthAdapter implements IAuthAdapter {
  private readonly auth: Auth
  private readonly httpAuth?: HttpAuthAdapter

  constructor(config: FirebaseAuthAdapterConfig) {
    this.auth = config.auth
    this.httpAuth = config.httpAuth
  }

  async signInWithEmailPassword(
    email: string,
    password: string,
  ): Promise<LoginResult> {
    try {
      const credential = await signInWithEmailAndPassword(this.auth, email, password)
      const user = toUser(credential.user)
      if (!user) return { message: LoginStatus.ERROR }
      return { message: LoginStatus.SUCCESS, user }
    } catch (err) {
      throw new AuthError(
        'auth/email-password-failed',
        'Firebase email/password sign-in failed.',
        { cause: err },
      )
    }
  }

  async signInWithEmailCode(
    email: string,
    code?: number,
  ): Promise<LoginResult> {
    if (!this.httpAuth) {
      throw new AuthError(
        'auth/missing-http-adapter',
        'FirebaseAuthAdapter.signInWithEmailCode requires an HttpAuthAdapter.',
      )
    }

    if (code === undefined) {
      return this.httpAuth.signInWithEmailCode(email)
    }

    const token = await this.httpAuth.exchangeEmailCodeForToken(email, code)
    if (!token) {
      return { message: LoginStatus.INVALID_CODE }
    }

    try {
      const credential = await signInWithCustomToken(this.auth, token)
      const user = toUser(credential.user)
      if (!user) return { message: LoginStatus.ERROR }
      return { message: LoginStatus.SUCCESS, user }
    } catch (err) {
      throw new AuthError(
        'auth/custom-token-failed',
        'Failed to exchange custom token from /api/auth.',
        { cause: err },
      )
    }
  }

  async signInWithOAuth(
    provider: OAuthProvider,
    options?: OAuthSignInOptions,
  ): Promise<LoginResult> {
    if (provider !== 'google') {
      throw new AuthError(
        'auth/oauth-unsupported',
        `OAuth provider "${provider}" is not yet supported by FirebaseAuthAdapter.`,
      )
    }

    const googleProvider = new GoogleAuthProvider()
    try {
      if (options?.redirect !== false) {
        await signInWithRedirect(this.auth, googleProvider)
        return { message: LoginStatus.SUCCESS }
      }
      const credential = await signInWithPopup(this.auth, googleProvider)
      const user = toUser(credential.user)
      if (!user) return { message: LoginStatus.ERROR }
      return { message: LoginStatus.SUCCESS, user }
    } catch (err) {
      throw new AuthError(
        'auth/oauth-failed',
        'Firebase Google sign-in failed.',
        { cause: err },
      )
    }
  }

  async signOut(): Promise<void> {
    try {
      await firebaseSignOut(this.auth)
    } catch (err) {
      throw new AuthError('auth/signout-failed', 'Firebase signOut failed.', {
        cause: err,
      })
    }
  }

  async getCurrentUser(): Promise<User | null> {
    return toUser(this.auth.currentUser)
  }

  onAuthStateChanged(listener: (user: User | null) => void): () => void {
    return firebaseOnAuthStateChanged(this.auth, (fb) => listener(toUser(fb)))
  }

  async getIdToken(): Promise<string | null> {
    const current = this.auth.currentUser
    if (!current) return null
    try {
      return await current.getIdToken()
    } catch {
      return null
    }
  }
}
