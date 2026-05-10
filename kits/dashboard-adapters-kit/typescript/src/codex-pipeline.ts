import { AgentPipelineAdapter } from "./base.js";
import type { PipelineEvent, RawAgentEvent } from "./types.js";

/**
 * Codex pipeline adapter.
 *
 * Translates Codex JSONL events into the unified Pipeline Protocol format.
 */
export class CodexPipelineAdapter extends AgentPipelineAdapter {
	translate(event: RawAgentEvent): PipelineEvent | null {
		const eventType = event.type as string;

		switch (eventType) {
			case "thread.started":
				return this.makeEvent("pipeline.started", {
					threadId: event.thread_id ?? (event.data as Record<string, unknown>)?.thread_id,
				});

			case "item.completed":
				return this.makeEvent("pipeline.output", {
					output: event.output ?? (event.data as Record<string, unknown>)?.output ?? "",
					itemType: event.item_type,
				});

			case "turn.completed":
				return this.makeEvent("pipeline.completed", {
					usage: event.usage ?? (event.data as Record<string, unknown>)?.usage,
				});

			case "tool.started":
				return this.makeEvent("pipeline.tool_use", {
					name: event.name ?? (event.data as Record<string, unknown>)?.name,
					args: event.arguments ?? (event.data as Record<string, unknown>)?.arguments,
				});

			case "tool.completed":
				return this.makeEvent("pipeline.step_completed", {
					name: event.name ?? (event.data as Record<string, unknown>)?.name,
					result: event.result ?? (event.data as Record<string, unknown>)?.result,
				});

			case "error":
				return this.makeEvent("pipeline.error", {
					message: event.message ?? String(event.error ?? "Unknown error"),
					code: event.code,
				});

			default:
				return null;
		}
	}
}
