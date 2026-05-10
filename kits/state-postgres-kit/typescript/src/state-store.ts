import type { IStateStore } from "../../../src/domain/ports.js";

/**
 * PostgreSQL state store for durable workflow checkpoints.
 * Requires `pg` as a peer dependency.
 *
 * @implements {IStateStore}
 */
export class PostgresStateStore implements IStateStore {
	async save(_workflowId: string, _state: Record<string, unknown>): Promise<void> {
		throw new Error("PostgresStateStore not yet implemented — install pg and configure connection");
	}

	async load(_workflowId: string): Promise<Record<string, unknown> | null> {
		throw new Error("PostgresStateStore not yet implemented");
	}

	async delete(_workflowId: string): Promise<void> {
		throw new Error("PostgresStateStore not yet implemented");
	}
}
