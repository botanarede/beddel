# @botanarede/bonarjs-sdk-alpha

Provider-agnostic TypeScript SDK that unifies the legacy `bonarjs-sdk`
(client-side, React, Firebase-coupled) and `bonar-cms-api` (Next.js App
Router backend, Firestore) into a single npm package.

The first release ships a Firebase provider so existing apps keep working
unchanged, but nothing in the core layer imports Firebase.

## Entry points

| Path                                             | Purpose                                          |
| ------------------------------------------------ | ------------------------------------------------ |
| `@botanarede/bonarjs-sdk-alpha`                  | Core + HTTP adapters + use cases                 |
| `@botanarede/bonarjs-sdk-alpha/react`            | React context + hooks                            |
| `@botanarede/bonarjs-sdk-alpha/server`           | Next.js route-handler utilities + guards         |
| `@botanarede/bonarjs-sdk-alpha/firebase`         | Firebase provider                                |

## Documentation

- [Architecture](./docs/ARCHITECTURE.md)
- [API reference](./docs/API-REFERENCE.md)
- [Migration guide](./docs/MIGRATION-GUIDE.md)
- [Testing strategy](./docs/TESTING-STRATEGY.md)

## Quick start

```ts
import { createFirebaseProvider } from '@botanarede/bonarjs-sdk-alpha/firebase'
import { HttpDatabaseAdapter, HttpAuthAdapter, StorageCacheAdapter, GetItems, SetItem } from '@botanarede/bonarjs-sdk-alpha'

const firebase = createFirebaseProvider({ firebaseConfig })

const database = new HttpDatabaseAdapter({
  apiUrl: 'https://api.example.com',
  apiKey: 'customer-id',
  tokenProvider: firebase.tokenProvider,
})
const cache = new StorageCacheAdapter({
  storage: firebase.storage,
  bucketUrlPattern: `https://firebasestorage.googleapis.com/v0/b/${firebaseConfig.storageBucket}/o/public%2Fcache%2F{file}.json?alt=media`,
})

const items = await new GetItems(database).execute('agenda')
await new SetItem(database, cache).execute('agenda', { title: 'Show', date: Date.now() })
```

## Scripts

```bash
npm run typecheck
npm run test
npm run build
```

See [`docs/TESTING-STRATEGY.md`](./docs/TESTING-STRATEGY.md) for the test
layout and coverage targets.
