import { AdapterError } from "../../../src/domain/errors.js";
import type { PipelineEvent, RawAgentEvent } from "./types.js";

/**
 * Abstract base class for dashboard pipeline adapters.
 *
 * Subclasses implement `translate()` to map backend-specific agent events
 * into the unified Pipeline Protocol format for SSE streaming to the dashboard.
 */
export abstract class AgentPipelineAdapter {
	protected readonly agentId: string;
	protected readonly traceUrl: string | undefined;

	constructor(agentId: string, traceUrl?: string) {
		this.agentId = agentId;
		this.traceUrl = traceUrl;
	}

	/**
	 * Translate a raw agent event into a unified PipelineEvent.
	 *
	 * @param event - Raw event from the agent backend.
	 * @returns Pipeline event, or `null` if the event should be filtered out.
	 * @throws {AdapterError} `BEDDEL-ADAPT-513` if the event cannot be translated.
	 */
	abstract translate(event: RawAgentEvent): PipelineEvent | null;

	/**
	 * Format a PipelineEvent as an SSE data line.
	 */
	toSSE(event: PipelineEvent): string {
		return `data: ${JSON.stringify(event)}\n\n`;
	}

	protected makeEvent(
		type: PipelineEvent["type"],
		data: Record<string, unknown>,
	): PipelineEvent {
		const event: PipelineEvent = {
			type,
			timestamp: new Date().toISOString(),
			agentId: this.agentId,
			data,
		};

		if (this.traceUrl) {
			event.traceUrl = this.traceUrl;
		}

		return event;
	}

	protected translationError(raw: RawAgentEvent, reason: string): AdapterError {
		return new AdapterError(
			"BEDDEL-ADAPT-513",
			`Cannot translate ${raw.type ?? "unknown"} event: ${reason}`,
			{ rawEventType: raw.type },
		);
	}
}
