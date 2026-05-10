import type { IMemoryProvider } from "../../../src/domain/ports.js";
import type { Episode, MemoryEntry } from "../../../src/domain/models.js";

/**
 * Google Vertex AI Memory Bank provider.
 * Requires @google-cloud/vertexai as a peer dependency.
 */
export class VertexMemoryProvider implements IMemoryProvider {
	async get(_key: string): Promise<unknown | null> {
		throw new Error("VertexMemoryProvider not yet implemented");
	}
	async set(_key: string, _value: unknown): Promise<void> {
		throw new Error("VertexMemoryProvider not yet implemented");
	}
	async search(_query: string, _topK?: number): Promise<MemoryEntry[]> {
		throw new Error("VertexMemoryProvider not yet implemented");
	}
	async listEpisodes(_workflowId: string): Promise<Episode[]> {
		throw new Error("VertexMemoryProvider not yet implemented");
	}
}
