import type { IAuthAdapter } from '../core/interfaces/IAuthAdapter'
import type { ITokenProvider } from '../core/interfaces/ITokenProvider'
import type { User } from '../core/entities/User'
import type { LoginResult, OAuthProvider, OAuthSignInOptions } from '../core/types'
import { LoginStatus } from '../core/types'
import { AuthError } from '../core/errors'

/** Configuration for {@link HttpAuthAdapter}. */
export interface HttpAuthAdapterConfig {
  apiUrl: string
  apiKey: string
  tokenProvider?: ITokenProvider
  fetchImpl?: typeof fetch
}

/**
 * HTTP adapter implementing the auth endpoints served by `bonar-cms-api`.
 *
 * Implements {@link IAuthAdapter}. No Firebase imports — password / OAuth
 * sign-in is assumed to be delegated to a provider adapter (e.g. the
 * Firebase one) that wraps this adapter for custom-token exchange.
 */
export class HttpAuthAdapter implements IAuthAdapter {
  private readonly apiUrl: string
  private readonly apiKey: string
  private readonly tokenProvider?: ITokenProvider
  private readonly fetchImpl: typeof fetch

  constructor(config: HttpAuthAdapterConfig) {
    if (!config.apiUrl) {
      throw new AuthError(
        'auth/invalid-config',
        'HttpAuthAdapter requires a non-empty apiUrl.',
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
        /* ignore */
      }
      try {
        const idToken = await this.tokenProvider.getIdToken()
        if (idToken) headers['X-Firebase-IdToken'] = idToken
      } catch {
        /* ignore */
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
      throw new AuthError(
        'auth/network-error',
        `Network error while calling ${endpoint}`,
        { cause: err },
      )
    }
    if (!response.ok) {
      throw new AuthError(
        'auth/http-error',
        `Auth API request failed: ${response.status} ${response.statusText}`,
        { status: response.status },
      )
    }
    return (await response.json()) as T
  }

  /**
   * Password sign-in is delegated to a concrete provider. The HTTP auth
   * adapter alone cannot verify passwords (the API has no such endpoint);
   * it still exists on the interface so React hooks can stay provider
   * agnostic. Consumers that call it directly get a deterministic error.
   */
  async signInWithEmailPassword(
    _email: string,
    _password: string,
  ): Promise<LoginResult> {
    throw new AuthError(
      'auth/unsupported',
      'HttpAuthAdapter does not implement password sign-in; use a provider adapter (e.g. FirebaseAuthAdapter).',
    )
  }

  async signInWithEmailCode(email: string, code?: number): Promise<LoginResult> {
    if (!email) {
      return { message: LoginStatus.INVALID_EMAIL }
    }

    if (code === undefined) {
      try {
        await this.request<{ message?: string }>('/api/auth', { email })
        return { message: LoginStatus.EMAIL_SENT }
      } catch (err) {
        if (err instanceof AuthError) throw err
        return { message: LoginStatus.ERROR }
      }
    }

    try {
      const response = await this.request<{ token?: string }>(
        '/api/auth',
        { email, code },
      )
      if (!response.token) {
        return { message: LoginStatus.INVALID_CODE }
      }
      return {
        message: LoginStatus.SUCCESS,
        user: { email } as User,
      }
    } catch (err) {
      if (err instanceof AuthError) throw err
      return { message: LoginStatus.ERROR }
    }
  }

  async signInWithOAuth(
    _provider: OAuthProvider,
    _options?: OAuthSignInOptions,
  ): Promise<LoginResult> {
    throw new AuthError(
      'auth/unsupported',
      'HttpAuthAdapter does not implement OAuth sign-in; use a provider adapter (e.g. FirebaseAuthAdapter).',
    )
  }

  async signOut(): Promise<void> {
    /* HTTP-only sign-out is a no-op — session lives in the auth provider. */
  }

  async getCurrentUser(): Promise<User | null> {
    return null
  }

  onAuthStateChanged(_listener: (user: User | null) => void): () => void {
    return () => {
      /* no-op */
    }
  }

  async getIdToken(): Promise<string | null> {
    if (!this.tokenProvider) return null
    try {
      return await this.tokenProvider.getIdToken()
    } catch {
      return null
    }
  }

  /**
   * Exchange an email + verification code for a Firebase custom token.
   * Returns `null` when the code is invalid.
   *
   * This is exposed so provider adapters (e.g. {@link FirebaseAuthAdapter})
   * can do the custom-token hand-off without re-implementing the request
   * plumbing. The generic {@link IAuthAdapter.signInWithEmailCode} remains
   * the recommended entry point for consumer code.
   */
  async exchangeEmailCodeForToken(
    email: string,
    code: number,
  ): Promise<string | null> {
    const response = await this.request<{ token?: string }>(
      '/api/auth',
      { email, code },
    )
    return response.token ?? null
  }

  /**
   * Call `/api/auth/checkUserInDatabase` to know whether `email` is already
   * registered. Surfaced on the adapter (not the interface) because it is a
   * Bonar-specific endpoint.
   */
  async checkUserInDatabase(email: string): Promise<boolean> {
    const data = await this.request<unknown>(
      '/api/auth/checkUserInDatabase',
      { email },
    )
    return Boolean(data)
  }

  /**
   * Call `/api/auth/verifyAppCheck` and return a short-lived custom App Check
   * token. Returns `null` when the endpoint declines to issue a token.
   */
  async fetchAppCheckToken(): Promise<{
    token: string
    expireTimeMillis: number
  } | null> {
    const data = await this.request<{ token?: string }>(
      '/api/auth/verifyAppCheck',
      {},
    )
    if (!data?.token) return null
    return { token: data.token, expireTimeMillis: Date.now() + 3600_000 }
  }
}
