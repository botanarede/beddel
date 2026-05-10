/**
 * SQLiteEventStore — IEventStore adapter backed by better-sqlite3.
 * AD-1: SQLite for IEventStore MVP.
 *
 * Schema: events(workflow_id, step_id, event_type, data_json, timestamp)
 * Exactly-once: UNIQUE(workflow_id, step_id, event_type) prevents duplicate checkpoints.
 *
 * NOTE: This file lives in a kit and is NOT imported by core. The kit boundary
 * rule means better-sqlite3 stays outside the core dependency graph.
 * This file is a reference implementation — it is not compiled or tested
 * as part of the core `pnpm run gates` pipeline. Integration tests belong
 * in the kit's own test suite once the kit is installed standalone.
 */

// Type-only import — the actual runtime import happens in the kit consumer
import type { BeddelEvent } from "@beddel/core";

interface Database {
	prepare(sql: string): Statement;
	exec(sql: string): void;
}

interface Statement {
	run(...params: unknown[]): void;
	all(...params: unknown[]): Record<string, unknown>[];
}

export class SQLiteEventStore {
	private readonly db: Database;

	constructor(db: Database) {
		this.db = db;
		this.db.exec(`
			CREATE TABLE IF NOT EXISTS events (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				workflow_id TEXT NOT NULL,
				step_id TEXT NOT NULL,
				event_type TEXT NOT NULL,
				data_json TEXT NOT NULL DEFAULT '{}',
				timestamp REAL NOT NULL,
				UNIQUE(workflow_id, step_id, event_type)
			)
		`);
	}

	async append(workflowId: string, stepId: string, event: BeddelEvent): Promise<void> {
		this.db
			.prepare(
				"INSERT OR REPLACE INTO events (workflow_id, step_id, event_type, data_json, timestamp) VALUES (?, ?, ?, ?, ?)",
			)
			.run(
				workflowId,
				stepId,
				event.event_type,
				JSON.stringify(event.data),
				event.timestamp,
			);
	}

	async load(workflowId: string): Promise<BeddelEvent[]> {
		const rows = this.db
			.prepare("SELECT * FROM events WHERE workflow_id = ? ORDER BY id")
			.all(workflowId);
		return rows.map((row) => ({
			event_type: row.event_type as string,
			step_id: row.step_id as string,
			data: JSON.parse(row.data_json as string),
			timestamp: row.timestamp as number,
		})) as BeddelEvent[];
	}

	async truncate(workflowId: string): Promise<void> {
		this.db.prepare("DELETE FROM events WHERE workflow_id = ?").run(workflowId);
	}
}
