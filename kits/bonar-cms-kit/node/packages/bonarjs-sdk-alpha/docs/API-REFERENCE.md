# API Reference

All public symbols in `@botanarede/bonarjs-sdk-alpha` are listed here. Types
are shown inline; examples assume TypeScript 5+.

The package uses **named exports only**. Do not expect default exports.

## 1. Core

Imported from `@botanarede/bonarjs-sdk-alpha`.

### 1.1 Entities

Each entity is a [Zod](https://zod.dev/) schema plus its inferred type.

#### `UserSchema` / `User`

```ts
import { UserSchema, type User } from '@botanarede/bonarjs-sdk-alpha'

const user: User = UserSchema.parse({ email: 'a@b.com', name: 'Ada' })
```

| Field | Type     | Required | Notes                      |
| ----- | -------- | :------: | -------------------------- |
| id    | string   |          | Provider-assigned user id  |
| name  | string   |          | Display name               |
| email | string   |    ✓     | Must pass `z.string().email()` |

#### `DynamicTableSchema` / `DynamicTable`

```ts
import { DynamicTableSchema, type DynamicTable } from '@botanarede/bonarjs-sdk-alpha'
```

| Field | Type     | Required | Notes                      |
| ----- | -------- | :------: | -------------------------- |
| id    | string   |          | Table id                   |
| name  | string   |          | Human-readable name        |
| items | unknown  |          | Collection items (free)    |

#### `EventSchema` / `Event`

```ts
import { EventSchema, type Event, validateAndConvertEvent } from '@botanarede/bonarjs-sdk-alpha'
```

| Field       | Type                         | Required | Notes                                         |
| ----------- | ---------------------------- | :------: | --------------------------------------------- |
| id          | string                       |    ✓     |                                               |
| title       | string                       |    ✓     |                                               |
| description | string                       |    ✓     |                                               |
| date        | number                       |          | Epoch ms (public API)                         |
| image       | string                       |    ✓     | URL or asset path                             |
| link        | string                       |          |                                               |
| location    | string                       |    ✓     |                                               |
| time        | string                       |    ✓     | `"HH:mm"`                                     |
| archived    | boolean                      |          |                                               |
| slug        | string                       |          |                                               |
| tags        | string[]                     |          |                                               |
| attendees   | number                       |          |                                               |

### 1.2 Interfaces

All interfaces live in `src/core/interfaces/`.

#### `IAuthAdapter`

```ts
interface IAuthAdapter {
  signInWithEmailPassword(email: string, password: string): Promise<LoginResult>
  signInWithEmailCode(email: string, code?: number): Promise<LoginResult>
  signInWithOAuth(provider: OAuthProvider, options?: { redirect?: boolean }): Promise<LoginResult>
  signOut(): Promise<void>
  getCurrentUser(): Promise<User | null>
  onAuthStateChanged(listener: (user: User | null) => void): () => void
  getIdToken(): Promise<string | null>
}
```

#### `IDatabaseAdapter`

```ts
interface IDatabaseAdapter {
  getItems<T = unknown>(table: string, options?: QueryOptions): Promise<T[]>
  getItemById<T = unknown>(table: string, id: string): Promise<T | null>
  setItem<T = unknown>(table: string, data: object, id?: string, events?: EventType): Promise<T>
  deleteItemById(table: string, id: string): Promise<{ success: true }>
  getItemChildById<T = unknown>(table: string, itemId: string, childName: string, childId: string): Promise<T | null>
}
```

#### `IStorageAdapter`

```ts
interface IStorageAdapter {
  uploadJSON(path: string, data: unknown, metadata?: StorageMetadata): Promise<void>
  getDownloadURL(path: string): Promise<string>
  deleteObject(path: string): Promise<void>
}
```

#### `ICacheAdapter`

```ts
interface ICacheAdapter {
  getCachedItems<T = unknown>(table: string, variant?: CacheVariant): Promise<T[] | null>
  updateCache(table: string, items: unknown[]): Promise<void>
  invalidate(table: string): void
}
```

#### `IMailAdapter`

```ts
interface IMailAdapter {
  send(payload: MailPayload): Promise<void>
}
```

#### `ITokenProvider`

```ts
interface ITokenProvider {
  getAppCheckToken(): Promise<string>
  getIdToken(): Promise<string | null>
}
```

### 1.3 Types

```ts
type AuthProvider = 'email' | 'google' | 'facebook'
type OAuthProvider = 'google' | 'facebook'
type EventType = 'EMAIL' | 'TICKET' | 'NONE'
type CacheVariant = 'upcoming' | 'schemas' | string

enum LoginStatus { SUCCESS, EMAIL_SENT, INVALID_CODE, INVALID_EMAIL, ERROR }

interface LoginResult { message: LoginStatus; user?: User }

interface QueryOptions {
  where?: { field: string; op: FirestoreOp; value: unknown }
  orderBy?: { field: string; direction?: 'asc' | 'desc' }
  limit?: number
  cacheVariant?: CacheVariant
}

interface ApiTokenProvider {
  getAppCheckToken: () => Promise<string>
  getIdToken: () => Promise<string | null>
}
```

### 1.4 Utilities

#### `timestamps`

```ts
import { toDate, dateToMillis, nowMillis, sortByDate, TIMESTAMP_FIELDS } from '@botanarede/bonarjs-sdk-alpha'

toDate(1_700_000_000_000) // Date
toDate(new Date())        // Date
dateToMillis(new Date())  // 1_700_000_000_000
nowMillis()               // Date.now()
sortByDate(a, b, 'date', 'asc')
```

#### `slugify`

```ts
import { generateSlug } from '@botanarede/bonarjs-sdk-alpha'

generateSlug('Café com Leite!') // 'cafe-com-leite'
```

#### `validation`

```ts
import { validateEmail, validateRequired } from '@botanarede/bonarjs-sdk-alpha'

validateEmail('a@b.com') // true
validateRequired({ name: 'Ada' }, ['name', 'email']) // throws ValidationError
```

### 1.5 Errors

```ts
import { BonarJsError, AuthError, DatabaseError, CacheError, ValidationError } from '@botanarede/bonarjs-sdk-alpha'

try { /* … */ } catch (err) {
  if (err instanceof DatabaseError) console.error(err.code, err.status)
}
```

Every error has `code: string` and optional `status?: number` plus `cause?:
unknown`. `BonarJsError` is the base class and sets `name` to the subclass
name.

## 2. Adapters

Imported from `@botanarede/bonarjs-sdk-alpha`.

### `HttpDatabaseAdapter`

```ts
new HttpDatabaseAdapter({
  apiUrl: string          // e.g. 'https://api.example.com'
  apiKey: string          // customer id — goes in Authorization
  tokenProvider?: ITokenProvider  // App Check + ID Token
})
```

Wire contract (matches `bonar-cms-api`):

- `POST /api/tables/getItems` → `{ content }`
- `POST /api/tables/getItemById` → `{ content }`
- `POST /api/tables/setItem` → `{ item, message }` (200 update / 201 create)
- `POST /api/tables/deleteItemById` → `{ success: true }`
- `POST /api/tables/getItemChildById` → `{ content }`

Timestamps in `createdAt`, `date`, `updated_at`, `updatedAt`, `created_at` are
normalized both ways automatically.

### `HttpAuthAdapter`

```ts
new HttpAuthAdapter({
  apiUrl: string
  apiKey: string
  tokenProvider?: ITokenProvider
})
```

Covers `/api/auth`, `/api/auth/verifyAppCheck`, `/api/auth/checkUserInDatabase`.

### `HttpMailAdapter`

```ts
new HttpMailAdapter({
  apiUrl: string
  apiKey: string
  tokenProvider?: ITokenProvider
  endpoint?: string // default '/api/mail/dispatchEventTicket'
})
```

### `StorageCacheAdapter`

```ts
new StorageCacheAdapter({
  storage: IStorageAdapter
  bucketUrlPattern: string   // e.g. 'https://firebasestorage.googleapis.com/v0/b/my-bucket/o/public%2Fcache%2F{file}.json?alt=media'
  publicTables?: string[]    // default ['agenda', 'metadata']
  business?: BusinessInfo    // used to build JSON-LD for events
})
```

The upcoming variant generator filters archived items, drops events with a
`date` older than midnight today, sorts by date ascending, and caps at 20.

## 3. Use cases

Each use case is a class with a single `execute()` method. All of them live
in `src/core/useCases/`.

```ts
new GetItems(database).execute(table, options?)
new GetItemById(database).execute(table, id)
new GetItemChildById(database).execute(table, itemId, childName, childId)
new SetItem(database, cache).execute(table, data, id?, events?)
new DeleteItemById(database, cache).execute(table, id)
new RefreshCache(database, cache).execute(table) // 2 attempts, 1s delay

new SignInEmailPassword(auth).execute(email, password)
new SignInEmailCode(auth).execute(email, code?)
new SignInOAuth(auth).execute(provider, options?)
new SignOut(auth).execute()
new GetCurrentUser(auth).execute()

new SendMail(mail).execute(payload)
```

## 4. Firebase provider

Imported from `@botanarede/bonarjs-sdk-alpha/firebase`.

```ts
import {
  createFirebaseProvider,
  FirebaseAuthAdapter,
  FirebaseStorageAdapter,
  FirebaseTokenProvider,
  initializeFirebase,
} from '@botanarede/bonarjs-sdk-alpha/firebase'

const firebase = createFirebaseProvider({
  firebaseConfig: {
    apiKey, authDomain, projectId, storageBucket,
    messagingSenderId, appId, databaseURL,
  },
  useEmulators: false,
  emulatorHost: 'localhost',
  emulatorPorts: { auth: 9099, firestore: 8080, storage: 9199 },
})

// firebase.auth           — IAuthAdapter
// firebase.storage        — IStorageAdapter
// firebase.tokenProvider  — ITokenProvider
// firebase.raw            — { app, auth, firestore, storage }
```

## 5. React integration

Imported from `@botanarede/bonarjs-sdk-alpha/react`.

```tsx
import {
  BonarJsProvider,
  useAuth,
  useDynamicTable,
  useMail,
  useBonarJs,
} from '@botanarede/bonarjs-sdk-alpha/react'

function App({ adapters }) {
  return (
    <BonarJsProvider adapters={adapters}>
      <MyScreen />
    </BonarJsProvider>
  )
}

function MyScreen() {
  const { user, loading, signInEmailPassword } = useAuth()
  const { getItems, setItem } = useDynamicTable()
  const { sendMail } = useMail()
  // …
}
```

`BonarJsProvider` accepts `{ auth, database, cache?, mail? }`. Hooks throw
`BonarJsError` if used outside the provider.

## 6. Server utilities

Imported from `@botanarede/bonarjs-sdk-alpha/server`.

```ts
import {
  guardRead,
  guardWrite,
  guardSmartWrite,
  makeGetItems,
  makeSetItem,
  makeDeleteItemById,
  makeGetItemById,
  serializeTimestamps,
  normalizeTimestamps,
  TIMESTAMP_FIELDS,
} from '@botanarede/bonarjs-sdk-alpha/server'
```

The `makeX` factories take `{ db, auth }` handles (`firebase-admin`) and
return Next.js App Router route handlers compatible with
`app/api/tables/*/route.ts`.
