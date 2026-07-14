import { getApps, initializeApp, type FirebaseApp, type FirebaseOptions } from 'firebase/app'
import {
  browserLocalPersistence,
  connectAuthEmulator,
  getAuth,
  indexedDBLocalPersistence,
  setPersistence,
  type Auth,
} from 'firebase/auth'
import {
  connectFirestoreEmulator,
  getFirestore,
  initializeFirestore,
  persistentLocalCache,
  persistentMultipleTabManager,
  type Firestore,
} from 'firebase/firestore'
import { connectStorageEmulator, getStorage, type FirebaseStorage } from 'firebase/storage'

/** Options for {@link initializeFirebase}. */
export interface InitializeFirebaseOptions {
  firebaseConfig: FirebaseOptions
  /** When true, wires up emulator connections for auth, firestore, storage. */
  useEmulators?: boolean
  emulatorHost?: string
  emulatorPorts?: {
    auth?: number
    firestore?: number
    storage?: number
  }
}

/** Return value of {@link initializeFirebase}. */
export interface InitializedFirebase {
  app: FirebaseApp
  auth: Auth
  firestore: Firestore
  storage: FirebaseStorage
}

function isSafari(): boolean {
  if (typeof navigator === 'undefined') return false
  return (
    navigator.userAgent.includes('Safari') &&
    !navigator.userAgent.includes('Chrome')
  )
}

/**
 * Canonical Firebase bootstrap for bonarjs apps.
 *
 * Handles:
 * - `initializeApp` idempotency (hot-reload safe).
 * - Safari-vs-others auth persistence selection.
 * - Firestore persistent cache with multi-tab manager.
 * - Optional emulator connections.
 */
export function initializeFirebase(
  options: InitializeFirebaseOptions,
): InitializedFirebase {
  const app = getApps().length === 0 ? initializeApp(options.firebaseConfig) : getApps()[0]!

  const auth = getAuth(app)

  let firestore: Firestore
  try {
    firestore = initializeFirestore(app, {
      localCache: persistentLocalCache({
        tabManager: persistentMultipleTabManager(),
      }),
    })
  } catch {
    firestore = getFirestore(app)
  }

  const storage = getStorage(app)

  if (typeof window !== 'undefined') {
    const persistence = isSafari()
      ? browserLocalPersistence
      : indexedDBLocalPersistence
    setPersistence(auth, persistence).catch((err) => {
      console.error('[bonarjs-sdk-alpha] Firebase persistence error:', err)
    })
  }

  if (options.useEmulators) {
    const host = options.emulatorHost ?? 'localhost'
    const authPort = options.emulatorPorts?.auth ?? 9099
    const firestorePort = options.emulatorPorts?.firestore ?? 8080
    const storagePort = options.emulatorPorts?.storage ?? 9199

    try {
      connectAuthEmulator(auth, `http://${host}:${authPort}`, {
        disableWarnings: true,
      })
    } catch {
      /* already connected */
    }
    try {
      connectFirestoreEmulator(firestore, host, firestorePort)
    } catch {
      /* already connected */
    }
    try {
      connectStorageEmulator(storage, host, storagePort)
    } catch {
      /* already connected */
    }
  }

  return { app, auth, firestore, storage }
}
