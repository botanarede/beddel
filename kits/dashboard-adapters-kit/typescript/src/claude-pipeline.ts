import { AgentPipelineAdapter } from "./base.js";
import type { PipelineEvent, RawAgentEvent } from "./types.js";

/**
 * Claude pipeline adapter.
 *
 * Translates Anthropic Messages API streaming events
 * into the unified Pipeline Protocol format.
 */
export class ClaudePipelineAdapter extends AgentPipelineAdapter {
	translate(event: RawAgentEvent): PipelineEvent | null {
		const eventType = event.type as string;

		switch (eventType) {
			case "content_block_delta":
				return this.makeEvent("pipeline.output", {
					content: event.text ?? "",
				});

			case "tool_use":
				return this.makeEvent("pipeline.tool_use", {
					name: event.name,
					input: event.input,
				});

			case "content_block_start":
				if ((event.content_block as Record<string, unknown>)?.type === "tool_use") {
					return this.makeEvent("pipeline.tool_use", {
						name: (event.content_block as Record<string, unknown>).name,
						input: (event.content_block as Record<string, unknown>).input,
					});
				}
				return this.makeEvent("pipeline.step_started", {
					blockType: (event.content_block as Record<string, unknown>)?.type,
					index: event.index,
				});

			case "message_start":
				return this.makeEvent("pipeline.started", {
					messageId: (event.message as Record<string, unknown>)?.id,
					model: (event.message as Record<string, unknown>)?.model,
				});

			case "message_stop":
				return this.makeEvent("pipeline.completed", {});

			case "message_delta":
				return this.makeEvent("pipeline.step_completed", {
					stopReason: (event.delta as Record<string, unknown>)?.stop_reason,
					usage: event.usage,
				});

			default:
				return null;
		}
	}
}
