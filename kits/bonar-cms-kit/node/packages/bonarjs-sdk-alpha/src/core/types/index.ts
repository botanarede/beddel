import type { User } from '../entities/User'

/** Auth provider name accepted by `SignIn.execute`. */
export type AuthProvider = 'email' | 'google' | 'facebook'

/** Subset of {@link AuthProvider} limited to OAuth providers. */
export type OAuthProvider = 'google' | 'facebook'

/** Side-effect hint passed to `setItem` to trigger downstream actions. */
export type EventType = 'EMAIL' | 'TICKET' | 'NONE'

/** Cache variant identifier understood by the cache adapter. */
export type CacheVariant = 'upcoming' | 'schemas' | (string & {})

/** Outcome of a login attempt. */
export enum LoginStatus {
  SUCCESS = 'Login efetuado com sucesso',
  EMAIL_SENT = 'Verifique o código enviado por email',
  INVALID_CODE = 'Código inválido',
  INVALID_EMAIL = 'Email inválido',
  ERROR = 'Erro inesperado',
}

/** Standard envelope returned by every auth use case. */
export interface LoginResult {
  message: LoginStatus
  user?: User
}

/** Supported Firestore filter operators (mirrors the upstream API). */
export type FirestoreOp =
  | '<'
  | '<='
  | '=='
  | '!='
  | '>='
  | '>'
  | 'array-contains'
  | 'array-contains-any'
  | 'in'
  | 'not-in'

/** Query options understood by {@link IDatabaseAdapter.getItems}. */
export interface QueryOptions {
  where?: { field: string; op: FirestoreOp; value: unknown }
  orderBy?: { field: string; direction?: 'asc' | 'desc' }
  limit?: number
  cacheVariant?: CacheVariant
}

/**
 * Pair of token accessors used by HTTP adapters to populate the
 * `X-Firebase-AppCheck` and `X-Firebase-IdToken` headers.
 */
export interface ApiTokenProvider {
  getAppCheckToken: () => Promise<string>
  getIdToken: () => Promise<string | null>
}

/** Optional metadata written alongside a storage object. */
export interface StorageMetadata {
  contentType?: string
  cacheControl?: string
  customMetadata?: Record<string, string>
}

/** Payload accepted by {@link IMailAdapter.send}. */
export interface MailPayload {
  to: string
  type?: string
  message?: {
    subject?: string
    html?: string
    text?: string
  }
  [key: string]: unknown
}

/** Business information used by {@link StorageCacheAdapter} to build JSON-LD. */
export interface BusinessInfo {
  siteUrl: string
  name: string
  id: string
  address?: {
    streetAddress?: string
    addressLocality?: string
    addressRegion?: string
    postalCode?: string
    addressCountry?: string
  }
  defaultDescriptionSuffix?: string
}

/** OAuth sign-in options. */
export interface OAuthSignInOptions {
  redirect?: boolean
}
