import { getToken, type AppCheck } from 'firebase/app-check'
import type { Auth } from 'firebase/auth'

import type { ITokenProvider } from '../../core/interfaces/ITokenProvider'

/** Configuration for {@link FirebaseTokenProvider}. */
export interface FirebaseTokenProviderConfig {
  appCheck: AppCheck
  auth: Auth
  /**
   * When true, `getAppCheckToken` forces App Check to refresh the token
   * instead of reusing the cached one. Defaults to `false`.
   */
  forceRefreshAppCheck?: boolean
}

/** ITokenProvider implementation backed by `firebase/app-check` + `firebase/auth`. */
export class FirebaseTokenProvider implements ITokenProvider {
  private readonly appCheck: AppCheck
  private readonly auth: Auth
  private readonly forceRefreshAppCheck: boolean

  constructor(config: FirebaseTokenProviderConfig) {
    this.appCheck = config.appCheck
    this.auth = config.auth
    this.forceRefreshAppCheck = config.forceRefreshAppCheck ?? false
  }

  async getAppCheckToken(): Promise<string> {
    const result = await getToken(this.appCheck, this.forceRefreshAppCheck)
    return result.token
  }

  async getIdToken(): Promise<string | null> {
    const current = this.auth.currentUser
    if (!current) return null
    return current.getIdToken()
  }
}
