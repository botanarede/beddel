# Architecture

`@botanarede/bonarjs-sdk-alpha` is a provider-agnostic TypeScript SDK that
unifies the behaviour of the legacy `bonarjs-sdk` (client hooks, Firebase
coupled) and `bonar-cms-api` (Next.js App Router backend, Firebase Admin /
Firestore) into a single npm package.

The guiding principle is the **adapter pattern**: the package defines a set of
minimal provider-agnostic interfaces (`IAuthAdapter`, `IDatabaseAdapter`,
`IStorageAdapter`, `ICacheAdapter`, `IMailAdapter`, `ITokenProvider`) that
consumers can implement against any backend. We ship a Firebase provider as
the first concrete implementation so existing apps keep working unchanged, but
nothing in the core pulls in Firebase.

## 1. Layer diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Consumers (apps)                             │
│   Next.js, React, Node services, any TS runtime                      │
└──────────────────────────────────────────────────────────────────────┘
                ▲                ▲                ▲
                │                │                │
┌───────────────┴────────────────┴────────────────┴────────────────────┐
│ 4. Integrations                                                      │
│    • react/         React context + hooks (peer: react)              │
│    • server/        Next.js route-handler utilities + guards         │
└──────────────────────────────────────────────────────────────────────┘
                ▲                                 ▲
                │                                 │
┌───────────────┴─────────────────────────────────┴────────────────────┐
│ 3. Providers                                                         │
│    • providers/firebase/  IAuthAdapter / IStorageAdapter /           │
│                           ITokenProvider implementations,            │
│                           FirebaseInitializer helper                 │
│    (future: providers/supabase, providers/rest, providers/sqlite…)   │
└──────────────────────────────────────────────────────────────────────┘
                ▲
                │
┌───────────────┴──────────────────────────────────────────────────────┐
│ 2. Adapters                                                          │
│    • HttpDatabaseAdapter   implements IDatabaseAdapter via fetch()   │
│    • HttpAuthAdapter       implements IAuthAdapter via fetch()       │
│    • HttpMailAdapter       implements IMailAdapter via fetch()       │
│    • StorageCacheAdapter   implements ICacheAdapter using            │
│                            IStorageAdapter + public CDN URL          │
└──────────────────────────────────────────────────────────────────────┘
                ▲
                │
┌───────────────┴──────────────────────────────────────────────────────┐
│ 1. Core (zero external dependencies except Zod)                      │
│    • entities/     User, DynamicTable, Event (Zod schemas)           │
│    • interfaces/   IAuthAdapter, IDatabaseAdapter, IStorageAdapter,  │
│                    ICacheAdapter, IMailAdapter, ITokenProvider       │
│    • types/        AuthProvider, EventType, LoginStatus,             │
│                    LoginResult, QueryOptions, CacheVariant…          │
│    • errors/       BonarJsError, AuthError, DatabaseError,           │
│                    CacheError, ValidationError                       │
│    • utils/        timestamps, slugify, validation                   │
│    • useCases/     Pure business logic on top of interfaces          │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. Layer responsibilities

### 2.1 Core (`src/core/`)

- Pure TypeScript, zero runtime dependencies other than [Zod](https://zod.dev/).
- Defines **entities** as Zod schemas so they can be validated at runtime and
  inferred at compile time.
- Defines **interfaces** describing every capability the SDK needs from a
  provider. These interfaces are the contract between the SDK and any backend.
- Defines **use cases** — small classes that compose interfaces to implement
  a specific business flow (e.g. "set item then refresh cache"). Use cases
  depend only on interfaces.
- Exposes **utilities** for timestamps (epoch-ms only), slug generation, and
  basic validation.
- MUST NOT import from `adapters/`, `providers/`, `react/`, or `server/`.

### 2.2 Adapters (`src/adapters/`)

- Concrete implementations of the core interfaces that are themselves provider
  agnostic — they rely on standard primitives (`fetch`, JSON, URLs).
- `HttpDatabaseAdapter` speaks the `bonar-cms-api` HTTP protocol over `fetch`.
- `HttpAuthAdapter` speaks the auth endpoints (`/api/auth`,
  `/api/auth/verifyAppCheck`, `/api/auth/checkUserInDatabase`) over `fetch`.
- `HttpMailAdapter` speaks the mail endpoint over `fetch`.
- `StorageCacheAdapter` reads the public cache from a configurable CDN URL
  and writes it through any `IStorageAdapter` (which is injected — the
  adapter itself never imports Firebase).
- MUST NOT import from `providers/`, `react/`, or `server/`.

### 2.3 Providers (`src/providers/`)

- Concrete provider bindings. Initial release ships **Firebase** only.
- `providers/firebase/` contains:
  - `FirebaseAuthAdapter` — implements `IAuthAdapter` using `firebase/auth`.
  - `FirebaseStorageAdapter` — implements `IStorageAdapter` using
    `firebase/storage`.
  - `FirebaseTokenProvider` — implements `ITokenProvider` using
    `firebase/app-check` + `firebase/auth`.
  - `FirebaseInitializer` — `initializeFirebase(config)` helper that takes
    care of app init, Safari-vs-others auth persistence, Firestore persistent
    cache, and emulator connections.
  - `createFirebaseProvider(config)` — wires all four into a single ready-to-
    use bundle.
- Future providers (Supabase, custom REST, SQLite) will live under
  `src/providers/<name>/` and be added to package exports.

### 2.4 Integrations (`src/react/`, `src/server/`)

- Optional subpaths exposed via package exports:
  - `@botanarede/bonarjs-sdk-alpha/react` — React context + hooks. Peer dep
    on `react` (optional).
  - `@botanarede/bonarjs-sdk-alpha/server` — Next.js route handlers and
    `authGuard` middleware. Peer dep on `firebase-admin` (optional).
- `react/` MUST NEVER import from `server/` and vice versa.

## 3. Client / server boundary

Every public entry point documents whether it runs on the client, the server,
or both:

| Entry point                                        | Client | Server | Notes                                    |
| -------------------------------------------------- | :----: | :----: | ---------------------------------------- |
| `@botanarede/bonarjs-sdk-alpha`                    |   ✓    |   ✓    | Core + HTTP adapters + use cases         |
| `@botanarede/bonarjs-sdk-alpha/react`              |   ✓    |        | Uses browser APIs (`window`, `React`)    |
| `@botanarede/bonarjs-sdk-alpha/server`             |        |   ✓    | Uses `firebase-admin`, `next/server`     |
| `@botanarede/bonarjs-sdk-alpha/firebase`           |   ✓    |        | Uses the client `firebase` SDK           |

The bundler does not enforce the boundary (tsup emits each entry as an
independent ESM chunk), but TypeScript imports between `react/` and `server/`
are forbidden by convention and enforced by the test suite.

## 4. The adapter pattern in practice

A consumer can plug any backend in four steps:

1. Implement the five provider interfaces (`IAuthAdapter`, `IDatabaseAdapter`,
   `IStorageAdapter`, `ICacheAdapter`, `IMailAdapter`). `ITokenProvider` is
   only needed if the chosen auth scheme issues tokens that the database
   adapter must forward.
2. Instantiate the adapters with provider-specific configuration.
3. Pass them into the use cases (`GetItems`, `SetItem`, `RefreshCache`, …).
4. Optionally plug the adapters into the React context via `BonarJsProvider`.

For the Firebase case, `createFirebaseProvider(config)` returns a record of
ready-to-use adapters and the raw Firebase handles, so a consumer can write:

```ts
import { createFirebaseProvider } from '@botanarede/bonarjs-sdk-alpha/firebase'
import { HttpDatabaseAdapter, HttpAuthAdapter, StorageCacheAdapter } from '@botanarede/bonarjs-sdk-alpha'

const firebase = createFirebaseProvider({ firebaseConfig, apiUrl, apiKey })

const database = new HttpDatabaseAdapter({
  apiUrl,
  apiKey,
  tokenProvider: firebase.tokenProvider,
})

const cache = new StorageCacheAdapter({
  storage: firebase.storage,
  bucketUrlPattern: `https://firebasestorage.googleapis.com/v0/b/${firebaseConfig.storageBucket}/o/public%2Fcache%2F{file}.json?alt=media`,
  publicTables: ['agenda', 'metadata'],
})
```

## 5. Timestamps

All timestamps on the public API are **epoch milliseconds (`number`)**. The
server-side `normalizeTimestamps` utility converts them to Firestore
`Timestamp` instances at write time, and `serializeTimestamps` converts them
back when reading. The known timestamp fields are:

```
createdAt, date, updated_at, updatedAt, created_at
```

This is consistent with the legacy `bonar-cms-api` behaviour.

## 6. Errors

The SDK defines a small error hierarchy in `src/core/errors/` so consumers can
`instanceof`-check what went wrong:

```
BonarJsError
├── AuthError           // auth flow failures, missing tokens
├── DatabaseError       // HTTP / adapter CRUD failures
├── CacheError          // cache read/write problems
└── ValidationError     // schema / argument validation
```

All errors carry a `code` string so they can be discriminated without
unstringy matching.
