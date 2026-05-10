# @beddel/state-postgres

PostgreSQL state persistence adapter for the Beddel TypeScript SDK.

## Installation

```bash
pnpm add @beddel/state-postgres pg
```

## Usage

```typescript
import { PostgresStateStore } from "@beddel/state-postgres";

const store = new PostgresStateStore({ connectionString: "postgres://..." });
```

## Status

Stub implementation. Full PostgreSQL integration planned for a future release.

## License

MIT
