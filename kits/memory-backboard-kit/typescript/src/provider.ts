import type { IMemoryProvider } from "../../../src/domain/ports.js";
import type { Episode, MemoryEntry } from "../../../src/domain/models.js";

/**
 * Backboard content-based memory provider.
 * Requires backboard-sdk as a peer dependency.
 */
export class BackboardMemoryProvider implements IMemoryProvider {
	async get(_key: string): Promise<unknown | null> {
		throw new Error("BackboardMemoryProvider not yet implemented");
	}
	async set(_key: string, _value: unknown): Promise<void> {
		throw new Error("BackboardMemoryProvider not yet implemented");
	}
	async search(_query: string, _topK?: number): Promise<MemoryEntry[]> {
		throw new Error("BackboardMemoryProvider not yet implemented");
	}
	async listEpisodes(_workflowId: string): Promise<Episode[]> {
		throw new Error("BackboardMemoryProvider not yet implemented");
	}
}
