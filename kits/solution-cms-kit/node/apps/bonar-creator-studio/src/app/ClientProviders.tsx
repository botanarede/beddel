'use client'

import {
  BonarJsProvider,
  type BonarJsAdapters,
} from '@botanarede/bonarjs-sdk-alpha/react'
import {
  HttpDatabaseAdapter,
  HttpMailAdapter,
} from '@botanarede/bonarjs-sdk-alpha'
import { createFirebaseProvider } from '@botanarede/bonarjs-sdk-alpha/firebase'
import { BehaviorDispatcherProvider } from '@botanarede/core/client'
import { useEffect, useState, useCallback, type ReactNode } from 'react'

const API_URL = process.env.NEXT_PUBLIC_URL_API ?? ''
const API_KEY = process.env.NEXT_PUBLIC_BONARJS_API_KEY ?? ''

/**
 * Noop database adapter for tenants that don't use a runtime API.
 * All data is resolved at build-time via cache/storage — runtime reads
 * return empty results gracefully.
 */
const NoopDatabaseAdapter = {
  getItems: async () => [],
  getItemById: async () => null,
  setItem: async () => ({}) as never,
  deleteItemById: async () => ({ success: true as const }),
  getItemChildById: async () => null,
}

/**
 * SSR/prerender-safe adapters. Keeps BonarJsProvider mounted during static
 * export and first client render so SDK hooks (useDynamicTable, etc.) used by
 * schema blocks never throw before the real client adapters initialize.
 */
const NoopAuthAdapter = {
  getCurrentUser: async () => null,
  onAuthStateChanged: () => () => {},
  signInEmailPassword: async () => null,
  signInOAuth: async () => null,
  signOut: async () => {},
  sendPasswordResetEmail: async () => {},
}

const SSR_SAFE_ADAPTERS = {
  auth: NoopAuthAdapter,
  database: NoopDatabaseAdapter,
} as unknown as BonarJsAdapters

function firebaseOptions() {
  return {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? '',
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? '',
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? '',
    storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET ?? '',
    messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID ?? '',
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? '',
  }
}

function buildAdapters(): BonarJsAdapters {
  const firebase = createFirebaseProvider({
    firebaseConfig: firebaseOptions(),
    recaptchaSiteKey:
      process.env.NEXT_PUBLIC_FIREBASE_APPCHECK_SITE_KEY || undefined,
  })

  // HttpDatabaseAdapter and HttpMailAdapter are optional — only created
  // when NEXT_PUBLIC_URL_API is defined. Tenants that rely solely on
  // build-time data resolution (cache/storage) don't need a runtime API.
  const database = API_URL
    ? new HttpDatabaseAdapter({
        apiUrl: API_URL,
        apiKey: API_KEY,
        tokenProvider: firebase.tokenProvider ?? undefined,
      })
    : NoopDatabaseAdapter

  const mail = API_URL
    ? new HttpMailAdapter({
        apiUrl: API_URL,
        apiKey: API_KEY,
        tokenProvider: firebase.tokenProvider ?? undefined,
      })
    : undefined

  return {
    auth: firebase.auth,
    database,
    ...(mail && { mail }),
  }
}

/**
 * Client-side SDK providers for bonar-creator-studio.
 *
 * Firebase Client SDK initializes only on the client side (deferred
 * via useEffect + useState) to ensure static export compatibility.
 * Hooks like useAuth(), useDynamicTable(), and useMail() become
 * available to any component in the tree.
 *
 * BehaviorDispatcherProvider from @botanarede/core enables declarative
 * behavior dispatch (navigation, dialogs, toasts, tab-sync) for
 * schema-driven components.
 */
export function ClientProviders({ children }: { children: ReactNode }) {
  const [adapters, setAdapters] = useState<BonarJsAdapters | null>(null)

  useEffect(() => {
    try {
      setAdapters(buildAdapters())
    } catch (err) {
      console.error('[ClientProviders] Failed to initialize SDK adapters:', err)
    }
  }, [])

  const handleRouteNavigate = useCallback((route: string) => {
    // Static export mode — no Next.js router available at runtime.
    // Use window.location for client-side navigation.
    if (typeof window !== 'undefined') {
      window.location.href = route
    }
  }, [])

  // Render children immediately — SDK hooks resolve against SSR-safe noop
  // adapters until the real client adapters are ready (after mount).
  return (
    <BehaviorDispatcherProvider onRouteNavigate={handleRouteNavigate}>
      <BonarJsProvider adapters={adapters ?? SSR_SAFE_ADAPTERS}>{children}</BonarJsProvider>
    </BehaviorDispatcherProvider>
  )
}
