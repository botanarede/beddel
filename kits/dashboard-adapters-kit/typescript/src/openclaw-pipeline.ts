import { AgentPipelineAdapter } from "./base.js";
import type { PipelineEvent, RawAgentEvent } from "./types.js";

/**
 * OpenClaw pipeline adapter.
 *
 * Translates OpenClaw Gateway SSE events (chat completion deltas)
 * into the unified Pipeline Protocol format.
 */
export class OpenClawPipelineAdapter extends AgentPipelineAdapter {
	translate(event: RawAgentEvent): PipelineEvent | null {
		const eventType = event.type as string | undefined;

		if (!eventType) {
			const choices = event.choices as Array<Record<string, unknown>> | undefined;
			if (choices?.[0]) {
				const delta = choices[0].delta as Record<string, unknown> | undefined;
				if (delta?.content) {
					return this.makeEvent("pipeline.output", {
						content: delta.content,
						model: event.model,
					});
				}
				if (delta?.tool_calls) {
					return this.makeEvent("pipeline.tool_use", {
						toolCalls: delta.tool_calls,
						model: event.model,
					});
				}
			}

			if (event.usage) {
				return this.makeEvent("pipeline.completed", {
					usage: event.usage,
					model: event.model,
				});
			}

			return null;
		}

		switch (eventType) {
			case "delta":
				return this.makeEvent("pipeline.output", {
					content: event.content ?? "",
				});

			case "task_completed":
				return this.makeEvent("pipeline.completed", {
					output: event.output,
					usage: event.usage,
				});

			case "error":
				return this.makeEvent("pipeline.error", {
					message: event.message ?? event.error ?? "Unknown error",
					code: event.code,
				});

			default:
				return null;
		}
	}
}
