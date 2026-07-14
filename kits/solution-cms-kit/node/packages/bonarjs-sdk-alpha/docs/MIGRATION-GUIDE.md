# Migration Guide: `bonarjs-sdk` → `bonarjs-sdk-alpha`

This guide covers moving an app from the in-monorepo `@botanarede/bonarjs-sdk`
to `@botanarede/bonarjs-sdk-alpha`. The two packages ship side by side during
the transition so you can migrate one app (or one hook) at a time.

## 1. Install

```bash
# from the monorepo root
yarn add @botanarede/bonarjs-sdk-alpha

# or for a standalone consumer
npm install @botanarede/bonarjs-sdk-alpha
```

Peer deps (`react`, `firebase`, `firebase-admin`) are optional — install them
only for the surface you actually use.

## 2. Public import map

| Legacy (`@/bonarjs-sdk-beta` / `@botanarede/bonarjs-sdk`)      | New (`@botanarede/bonarjs-sdk-alpha`)                        |
| -------------------------------------------------------------- | ------------------------------------------------------------ |
| `core/entities/User` `UserSchema`, `User`                      | `@botanarede/bonarjs-sdk-alpha`                              |
| `core/entities/DynamicTable` `DynamicTableSchema`, …           | `@botanarede/bonarjs-sdk-alpha`                              |
| `core/entities/Evento` `Evento`, `EventoType`                  | `@botanarede/bonarjs-sdk-alpha` as `Event`, `EventSchema`    |
| `core/types` `LoginStatus`, `LoginResult`, `ApiTokenProvider`  | `@botanarede/bonarjs-sdk-alpha`                              |
| `core/interfaces/IAuthRepository`                              | `IAuthAdapter` in `@botanarede/bonarjs-sdk-alpha`            |
| `core/interfaces/IDynamicTableRepository`                      | `IDatabaseAdapter` in `@botanarede/bonarjs-sdk-alpha`        |
| `core/interfaces/IMailRepository`                              | `IMailAdapter` in `@botanarede/bonarjs-sdk-alpha`            |
| `infrastructure/AuthRepository`                                | `HttpAuthAdapter` in `@botanarede/bonarjs-sdk-alpha`         |
| `infrastructure/DynamicTableRepository`                        | `HttpDatabaseAdapter` in `@botanarede/bonarjs-sdk-alpha`     |
| `infrastructure/PublicDataCacheService` (static class)         | `StorageCacheAdapter` in `@botanarede/bonarjs-sdk-alpha`     |
| `infrastructure/MailRepository`                                | `HttpMailAdapter` in `@botanarede/bonarjs-sdk-alpha`         |
| `lib/utils/initializeFirebase`                                 | `initializeFirebase` in `@botanarede/bonarjs-sdk-alpha/firebase` |
| `hooks/useBonarJsAuth`                                         | `useAuth` in `@botanarede/bonarjs-sdk-alpha/react`           |
| `hooks/useDynamicTable`                                        | `useDynamicTable` in `@botanarede/bonarjs-sdk-alpha/react`   |
| `hooks/useMail`                                                | `useMail` in `@botanarede/bonarjs-sdk-alpha/react`           |
| `presentation/providers/BonarJsAuthProvider`                   | Bundled inside `BonarJsProvider` from `…/react`              |

## 3. Key API changes

1. `setItem(table, data, events, id?)` is now
   `setItem(table, data, id?, events?)`. The argument order change makes `id`
   the primary optional argument since `events` is an optional side-effect
   hint most callers never set.
2. Class names now end in `Adapter` instead of `Repository` and use
   `IXxxAdapter` interfaces (legacy names are re-exported as deprecated
   aliases for one minor release).
3. `PublicDataCacheService` (static class, Firebase-coupled) is now
   `StorageCacheAdapter` (instance, storage-agnostic). It takes the bucket
   URL template and the list of public tables via config.
4. Firebase is **only** touched through `@botanarede/bonarjs-sdk-alpha/firebase`.
   `core/`, `adapters/`, `react/`, and `server/` never import Firebase.
5. All timestamps on the public API are epoch milliseconds. The
   `convertFirebaseDateToDate` helper is replaced by `toDate`.
6. Return types are now explicit (`Promise<T[]>`, `Promise<T | null>`) rather
   than `Promise<any>`. You may need to pass a type argument on first call.

## 4. Before / after

### 4.1 Bootstrap

**Before**

```ts
import { initializeFirebase } from '@/bonarjs-sdk-beta/lib/utils/initializeFirebase'
import { AuthRepository } from '@/bonarjs-sdk-beta/infrastructure/AuthRepository'
import { DynamicTableRepository } from '@/bonarjs-sdk-beta/infrastructure/DynamicTableRepository'

const { auth } = initializeFirebase()
const authRepo = new AuthRepository(auth)
const db = new DynamicTableRepository()
```

**After**

```ts
import { createFirebaseProvider } from '@botanarede/bonarjs-sdk-alpha/firebase'
import { HttpDatabaseAdapter, HttpAuthAdapter } from '@botanarede/bonarjs-sdk-alpha'

const firebase = createFirebaseProvider({ firebaseConfig })
const auth = new HttpAuthAdapter({
  apiUrl: process.env.NEXT_PUBLIC_URL_API!,
  apiKey: process.env.NEXT_PUBLIC_BONARJS_API_KEY!,
  tokenProvider: firebase.tokenProvider,
})
const database = new HttpDatabaseAdapter({
  apiUrl: process.env.NEXT_PUBLIC_URL_API!,
  apiKey: process.env.NEXT_PUBLIC_BONARJS_API_KEY!,
  tokenProvider: firebase.tokenProvider,
})
```

### 4.2 React

**Before**

```tsx
import { BonarJsClientProviders } from '@/bonarjs-sdk-beta/presentation/providers'
import { useDynamicTable } from '@/bonarjs-sdk-beta/hooks'

function App({ children }) {
  return <BonarJsClientProviders>{children}</BonarJsClientProviders>
}

function Screen() {
  const { handleGetItems, handleSetItem } = useDynamicTable()
  // …
}
```

**After**

```tsx
import { BonarJsProvider, useDynamicTable } from '@botanarede/bonarjs-sdk-alpha/react'

function App({ children }) {
  return (
    <BonarJsProvider adapters={{ auth, database, cache, mail }}>
      {children}
    </BonarJsProvider>
  )
}

function Screen() {
  const { getItems, setItem } = useDynamicTable()
  // …
}
```

### 4.3 API route handler

**Before** (`src/app/api/tables/getItems/route.ts` in `bonar-cms-api`)

```ts
import { NextResponse } from 'next/server'
import initializeFirebaseServer from '@/components/firebase-admin'
import { guardRead } from '@/lib/auth-guard'

const admin = initializeFirebaseServer()

export async function POST(req) {
  const err = await guardRead(req)
  if (err) return err
  // … manual query + serialize + response …
}
```

**After**

```ts
import { makeGetItems } from '@botanarede/bonarjs-sdk-alpha/server'
import initializeFirebaseServer from '@/components/firebase-admin'

const admin = initializeFirebaseServer()

export const POST = makeGetItems({ db: admin.db })
```

## 5. Deprecations

For one minor release we will re-export the legacy names from the new package:

```ts
// Deprecated aliases — will be removed in 0.2.0
export { HttpAuthAdapter as AuthRepository } from './adapters/HttpAuthAdapter'
export { HttpDatabaseAdapter as DynamicTableRepository } from './adapters/HttpDatabaseAdapter'
```

Run a codemod like the following in the meantime:

```bash
# repo root
grep -rl '@/bonarjs-sdk-beta' src | xargs sed -i 's|@/bonarjs-sdk-beta/infrastructure/AuthRepository|@botanarede/bonarjs-sdk-alpha|g'
```

## 6. Testing the migration

Each migrated app should:

1. Pass `tsc --noEmit` with the new imports.
2. Pass its unit / integration tests against both the legacy and the new
   adapters (keep a short-lived dual-import period if needed).
3. Hit one of the public endpoints in staging to confirm wire-format parity
   (the HTTP adapter sends identical headers and bodies).
