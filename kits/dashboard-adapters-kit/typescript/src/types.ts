/**
 * Unified pipeline event shape for the Beddel dashboard.
 * All agent backends normalize their events into this protocol.
 */
export interface PipelineEvent {
	type: PipelineEventType;
	timestamp: string;
	agentId: string;
	data: Record<string, unknown>;
	traceUrl?: string;
}

export type PipelineEventType =
	| "pipeline.started"
	| "pipeline.step_started"
	| "pipeline.step_completed"
	| "pipeline.output"
	| "pipeline.tool_use"
	| "pipeline.error"
	| "pipeline.completed";

/**
 * Raw event from any agent backend.
 */
export interface RawAgentEvent {
	type: string;
	[key: string]: unknown;
}
