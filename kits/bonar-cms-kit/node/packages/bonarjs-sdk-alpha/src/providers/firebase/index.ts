import { initializeAppCheck, ReCaptchaV3Provider, type AppCheck } from 'firebase/app-check'

import { FirebaseAuthAdapter, type FirebaseAuthAdapterConfig } from './FirebaseAuthAdapter'
import { FirebaseStorageAdapter } from './FirebaseStorageAdapter'
import { FirebaseTokenProvider } from './FirebaseTokenProvider'
import { initializeFirebase, type InitializeFirebaseOptions, type InitializedFirebase } from './FirebaseInitializer'
import type { HttpAuthAdapter } from '../../adapters/HttpAuthAdapter'

export {
  FirebaseAuthAdapter,
  type FirebaseAuthAdapterConfig,
} from './FirebaseAuthAdapter'
export {
  FirebaseStorageAdapter,
  type FirebaseStorageAdapterConfig,
} from './FirebaseStorageAdapter'
export {
  FirebaseTokenProvider,
  type FirebaseTokenProviderConfig,
} from './FirebaseTokenProvider'
export {
  initializeFirebase,
  type InitializeFirebaseOptions,
  type InitializedFirebase,
} from './FirebaseInitializer'

/** Options for {@link createFirebaseProvider}. */
export interface CreateFirebaseProviderOptions extends InitializeFirebaseOptions {
  /**
   * reCAPTCHA v3 site key used to initialise App Check. Omit to skip App
   * Check setup (the returned `tokenProvider` will throw when invoked).
   */
  recaptchaSiteKey?: string
  /** Forwarded to `initializeAppCheck`. Defaults to `true`. */
  appCheckAutoRefresh?: boolean
  /**
   * When provided, the Firebase auth adapter delegates email-code flows and
   * custom-token exchange to this HTTP auth adapter.
   */
  httpAuth?: HttpAuthAdapter
}

/**
 * Assembled Firebase provider — every adapter + the raw Firebase handles.
 */
export interface FirebaseProviderBundle {
  auth: FirebaseAuthAdapter
  storage: FirebaseStorageAdapter
  tokenProvider: FirebaseTokenProvider | null
  raw: InitializedFirebase & { appCheck: AppCheck | null }
}

/**
 * Wire every Firebase adapter together in one call.
 *
 * When `recaptchaSiteKey` is omitted, App Check is not initialised and
 * `tokenProvider` is `null` — useful in test environments.
 */
export function createFirebaseProvider(
  options: CreateFirebaseProviderOptions,
): FirebaseProviderBundle {
  const init = initializeFirebase(options)

  let appCheck: AppCheck | null = null
  let tokenProvider: FirebaseTokenProvider | null = null
  if (options.recaptchaSiteKey) {
    appCheck = initializeAppCheck(init.app, {
      provider: new ReCaptchaV3Provider(options.recaptchaSiteKey),
      isTokenAutoRefreshEnabled: options.appCheckAutoRefresh ?? true,
    })
    tokenProvider = new FirebaseTokenProvider({ appCheck, auth: init.auth })
  }

  const authAdapterConfig: FirebaseAuthAdapterConfig = { auth: init.auth }
  if (options.httpAuth) authAdapterConfig.httpAuth = options.httpAuth

  const auth = new FirebaseAuthAdapter(authAdapterConfig)
  const storage = new FirebaseStorageAdapter({ storage: init.storage })

  return {
    auth,
    storage,
    tokenProvider,
    raw: { ...init, appCheck },
  }
}
