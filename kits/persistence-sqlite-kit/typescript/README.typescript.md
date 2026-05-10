# persistence-sqlite-kit

SQLite-backed `IEventStore` adapter for Beddel durable execution (AD-1).

## Installation

```bash
pnpm add @beddel/persistence-sqlite better-sqlite3
```

## Usage

```typescript
import Database from "better-sqlite3";
import { SQLiteEventStore } from "@beddel/persistence-sqlite";

const db = new Database("./beddel-events.db");
const eventStore = new SQLiteEventStore(db);
```

## Exactly-Once Semantics

The schema uses a `UNIQUE(workflow_id, step_id, event_type)` constraint with
`INSERT OR REPLACE` to prevent duplicate checkpoint events during replay.
