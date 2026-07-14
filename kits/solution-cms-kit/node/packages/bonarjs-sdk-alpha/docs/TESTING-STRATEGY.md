# Testing Strategy

Tests live in `packages/bonarjs-sdk-alpha/tests/`, separate from `src/` so
they are stripped from the published `dist/`. The framework is
[Vitest](https://vitest.dev/), with [msw](https://mswjs.io/) used only for
HTTP-level mocking.

## 1. Layers

```
tests/
├── unit/               pure, no network, no I/O, no React
│   ├── core/           entity schemas, utils, errors
│   └── useCases/       business flows with mocked interfaces
├── integration/        with msw intercepting fetch
│   └── adapters/       HttpDatabase, HttpAuth, StorageCache
└── e2e/                end-to-end composition of adapters + use cases
```

## 2. What each layer tests

### 2.1 Unit

- **core/entities** — zod schemas accept all known-good payloads and reject
  malformed ones. Regression tests for every required/optional field.
- **core/utils/timestamps** — `toDate`, `dateToMillis`, `nowMillis`,
  `sortByDate`, edge cases (`0`, `null`, `Date`, ISO strings).
- **core/utils/slugify** — accents (`á`, `ê`), special chars (`!`, `?`, `"`),
  multiple spaces, leading/trailing dashes, ≥ 100 chars truncation.
- **core/errors** — class hierarchy, `instanceof BonarJsError`, `code`
  property, `cause` propagation.
- **useCases/getItems** — given an `IDatabaseAdapter` mock, archived items
  are filtered out.
- **useCases/setItem** — verifies `ICacheAdapter.updateCache` is called with
  the expected table and fresh items.
- **useCases/deleteItemById** — verifies cache invalidation + refresh.
- **useCases/refreshCache** — verifies retry logic (2 attempts with 1s delay)
  using Vitest fake timers.

### 2.2 Integration

- **HttpDatabaseAdapter** — msw mock server serves `POST /api/tables/*`
  routes, each test asserts request headers
  (`Authorization`, `X-Firebase-AppCheck`, `X-Firebase-IdToken`,
  `Content-Type`), body shape, response parsing, timestamp de/normalization,
  and error handling (401/500).
- **StorageCacheAdapter** — uses a spy `IStorageAdapter` + msw-mocked CDN
  URL; verifies the upcoming/schemas variants are written, the in-flight map
  dedupes concurrent reads, and `invalidate()` clears inflight entries.
- **HttpAuthAdapter** — msw intercepts `/api/auth`, `/api/auth/verifyAppCheck`,
  `/api/auth/checkUserInDatabase`; verifies the email-code flow returns
  `LoginStatus.EMAIL_SENT` then `LoginStatus.SUCCESS`.

### 2.3 E2E

- **auth-crud-cache** — bootstrap a full provider (mocked auth adapter +
  mocked tokens + in-memory cache + msw-mocked API), run the complete user
  journey: sign-in → create item → list items → delete item → verify cache
  refreshed. This is the safety net that catches composition bugs the
  unit/integration tests miss.

## 3. Coverage targets

Enforced via `vitest --coverage` in CI:

| Layer                     | Target |
| ------------------------- | :----: |
| `src/core/`               |  90 %  |
| `src/adapters/`           |  80 %  |
| `src/react/`              |  70 %  |
| `src/server/`             |  80 %  |
| `src/providers/firebase/` |  60 %  |

Firebase provider coverage is intentionally lower — the Firebase SDK itself
is assumed tested, our code is a thin adapter.

## 4. Running tests

```bash
# from packages/bonarjs-sdk-alpha
npm run test             # single run
npm run test:watch       # watch mode for dev
npm run test:coverage    # with coverage
npm run typecheck        # tsc --noEmit
npm run build            # tsup emits dist/
```

Each phase of development should end with all three of `typecheck`, `test`,
and `build` passing before the next phase starts (see `../README.md`).

## 5. Fixtures

Shared fixtures live in `tests/fixtures/`:

- `events.ts` — a set of `Event` objects covering archived, past, and future.
- `responses.ts` — typical API responses for `getItems`, `setItem`, `deleteItemById`.
- `fakeAdapters.ts` — in-memory implementations of every interface for tests
  that need a composable double.

## 6. Continuous integration

Any CI pipeline that runs the monorepo should add a `bonarjs-sdk-alpha` job:

```yaml
- name: bonarjs-sdk-alpha
  run: |
    cd packages/bonarjs-sdk-alpha
    npm ci
    npm run typecheck
    npm run test
    npm run build
```

Tests must never hit the network or a real Firebase project.
