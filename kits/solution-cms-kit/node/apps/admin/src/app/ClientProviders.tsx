'use client'

import {
  BonarJsProvider,
  type BonarJsAdapters,
} from '@botanarede/bonarjs-sdk-alpha/react'
import {
  HttpDatabaseAdapter,
  HttpMailAdapter,
  StorageCacheAdapter,
} from '@botanarede/bonarjs-sdk-alpha'
import { createFirebaseProvider } from '@botanarede/bonarjs-sdk-alpha/firebase'
import { useEffect, useState, type ReactNode } from 'react'

/**
 * API URL for SDK adapters.
 *
 * In dev: http://cms-admin.local:3001 (set via NEXT_PUBLIC_URL_API)
 * In prod: the production API domain
 *
 * Falls back to window.location.origin if env var is not set,
 * since API routes live in this same Next.js app.
 * buildAdapters() runs inside useEffect (browser only).
 */
function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_URL_API || window.location.origin
}

const API_KEY = process.env.NEXT_PUBLIC_BONARJS_API_KEY ?? ''
const STORAGE_BUCKET = process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET ?? ''

function firebaseOptions() {
  return {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? '',
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? '',
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? '',
    storageBucket: STORAGE_BUCKET,
    messagingSenderId:
      process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID ?? '',
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? '',
  }
}

function buildAdapters(): BonarJsAdapters {
  const firebase = createFirebaseProvider({
    firebaseConfig: firebaseOptions(),
    recaptchaSiteKey:
      process.env.NEXT_PUBLIC_FIREBASE_APPCHECK_SITE_KEY || undefined,
  })

  const database = new HttpDatabaseAdapter({
    apiUrl: getApiUrl(),
    apiKey: API_KEY,
    tokenProvider: firebase.tokenProvider ?? undefined,
  })

  const mail = new HttpMailAdapter({
    apiUrl: getApiUrl(),
    apiKey: API_KEY,
    tokenProvider: firebase.tokenProvider ?? undefined,
  })

  const cache = new StorageCacheAdapter({
    storage: firebase.storage,
    bucketUrlPattern: `https://firebasestorage.googleapis.com/v0/b/${STORAGE_BUCKET}/o/public%2Fcache%2F{file}.json?alt=media`,
    publicTables: ['agenda', 'metadata'],
    business: {
      name: 'Admin Panel',
      siteUrl: '',
      id: 'admin',
      address: {
        streetAddress: '',
        addressLocality: '',
        addressRegion: '',
        postalCode: '',
        addressCountry: '',
      },
    },
  })

  return { auth: firebase.auth, database, cache, mail }
}

/**
 * Wires bonarjs-sdk-alpha adapters into React context.
 *
 * Adapter construction is deferred to the browser (`useEffect`) so that
 * SSR does not try to initialise Firebase, which requires `window`.
 */
export function ClientProviders({ children }: { children: ReactNode }) {
  const [adapters, setAdapters] = useState<BonarJsAdapters | null>(null)

  useEffect(() => {
    setAdapters(buildAdapters())
  }, [])

  if (!adapters) return null
  return <BonarJsProvider adapters={adapters}>{children}</BonarJsProvider>
}
