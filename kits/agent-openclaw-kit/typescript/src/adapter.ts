import { AdapterError } from "../../../src/domain/errors.js";
import type { AgentResult, IAgentAdapter } from "../../../src/domain/ports.js";

export interface OpenClawAdapterConfig {
	gatewayUrl?: string;
	agent?: string;
	model?: string;
	timeoutMs?: number;
}

const SANDBOX_HEADERS: Record<string, Record<string, string>> = {
	"read-only": {},
	"workspace-write": { "x-tool-authorization": "workspace-write" },
	"danger-full-access": { "x-tool-authorization": "danger-full-access" },
};

/**
 * OpenClaw Gateway HTTP agent adapter.
 *
 * Sends `POST /v1/chat/completions` to the OpenClaw Gateway using Node 20's
 * builtin `fetch`. Zero runtime dependencies.
 *
 * @implements {IAgentAdapter}
 */
export class OpenClawAgentAdapter implements IAgentAdapter {
	private readonly gatewayUrl: string;
	private readonly agent: string;
	private readonly model: string | undefined;
	private readonly timeoutMs: number;

	constructor(config: OpenClawAdapterConfig = {}) {
		this.gatewayUrl = config.gatewayUrl ?? "http://localhost:3000";
		this.agent = config.agent ?? "main";
		this.model = config.model;
		this.timeoutMs = config.timeoutMs ?? 120_000;
	}

	async execute(
		prompt: string,
		options?: {
			model?: string;
			sandbox?: string;
			tools?: string[];
			outputSchema?: Record<string, unknown>;
		},
	): Promise<AgentResult> {
		const startTime = Date.now();
		const sandbox = options?.sandbox ?? "read-only";
		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

		const body = this.buildRequestBody(prompt, options);

		try {
			const response = await fetch(`${this.gatewayUrl}/v1/chat/completions`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					...SANDBOX_HEADERS[sandbox],
				},
				body: JSON.stringify(body),
				signal: controller.signal,
			});

			if (!response.ok) {
				const text = await response.text().catch(() => "(unreadable body)");
				throw new AdapterError(
					"BEDDEL-ADAPT-502",
					`OpenClaw Gateway returned HTTP ${response.status}`,
					{ status: response.status, body: text.slice(0, 500) },
				);
			}

			let data: Record<string, unknown>;
			try {
				data = (await response.json()) as Record<string, unknown>;
			} catch {
				throw new AdapterError(
					"BEDDEL-ADAPT-503",
					"OpenClaw Gateway returned invalid JSON",
				);
			}

			const durationMs = Date.now() - startTime;
			return this.parseResponse(data, durationMs);
		} catch (error) {
			if (error instanceof AdapterError) throw error;
			if (controller.signal.aborted) {
				throw new AdapterError(
					"BEDDEL-ADAPT-501",
					`OpenClaw Gateway request timed out after ${this.timeoutMs}ms`,
					{ timeoutMs: this.timeoutMs },
				);
			}
			throw new AdapterError(
				"BEDDEL-ADAPT-500",
				`Cannot reach OpenClaw Gateway: ${error instanceof Error ? error.message : String(error)}`,
				{ gatewayUrl: this.gatewayUrl },
			);
		} finally {
			clearTimeout(timeout);
		}
	}

	async *stream(
		prompt: string,
		options?: {
			model?: string;
			sandbox?: string;
			tools?: string[];
		},
	): AsyncGenerator<Record<string, unknown>, void, void> {
		const sandbox = options?.sandbox ?? "read-only";
		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
		const body = this.buildRequestBody(prompt, options);

		try {
			const response = await fetch(`${this.gatewayUrl}/v1/chat/completions`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					Accept: "text/event-stream",
					...SANDBOX_HEADERS[sandbox],
				},
				body: JSON.stringify(body),
				signal: controller.signal,
			});

			if (!response.ok) {
				const text = await response.text().catch(() => "(unreadable body)");
				throw new AdapterError(
					"BEDDEL-ADAPT-502",
					`OpenClaw Gateway returned HTTP ${response.status}`,
					{ status: response.status, body: text.slice(0, 500) },
				);
			}

			if (!response.body) {
				const result = await this.execute(prompt, options);
				yield {
					type: "task_completed",
					output: result.output,
					usage: result.usage,
				};
				return;
			}

			const reader = response.body.getReader();
			const decoder = new TextDecoder();
			let buffer = "";

			try {
				while (true) {
					const { done, value } = await reader.read();
					if (done) break;

					buffer += decoder.decode(value, { stream: true });
					const lines = buffer.split("\n");
					buffer = lines.pop() ?? "";

					for (const line of lines) {
						const trimmed = line.trim();
						if (!trimmed || trimmed.startsWith(":")) continue;
						if (trimmed === "data: [DONE]") return;

						if (trimmed.startsWith("data: ")) {
							const jsonStr = trimmed.slice(6);
							try {
								const parsed = JSON.parse(jsonStr) as Record<string, unknown>;
								yield parsed;
							} catch {
								throw new AdapterError(
									"BEDDEL-ADAPT-504",
									"SSE stream emitted a malformed event",
									{ rawLine: jsonStr.slice(0, 200) },
								);
							}
						}
					}
				}
			} finally {
				reader.releaseLock();
			}
		} catch (error) {
			if (error instanceof AdapterError) throw error;
			if (controller.signal.aborted) {
				throw new AdapterError(
					"BEDDEL-ADAPT-501",
					`OpenClaw Gateway stream timed out after ${this.timeoutMs}ms`,
					{ timeoutMs: this.timeoutMs },
				);
			}
			throw new AdapterError(
				"BEDDEL-ADAPT-500",
				`Cannot reach OpenClaw Gateway: ${error instanceof Error ? error.message : String(error)}`,
				{ gatewayUrl: this.gatewayUrl },
			);
		} finally {
			clearTimeout(timeout);
		}
	}

	private buildRequestBody(
		prompt: string,
		options?: {
			model?: string;
			sandbox?: string;
			tools?: string[];
			outputSchema?: Record<string, unknown>;
		},
	): Record<string, unknown> {
		const body: Record<string, unknown> = {
			messages: [{ role: "user", content: prompt }],
			agent: this.agent,
		};

		if (options?.model ?? this.model) {
			body.model = options?.model ?? this.model;
		}

		if (options?.tools) {
			body.tools = options.tools;
		}

		return body;
	}

	private parseResponse(
		data: Record<string, unknown>,
		durationMs: number,
	): AgentResult {
		const choices = data.choices as Array<Record<string, unknown>> | undefined;
		const firstChoice = choices?.[0] ?? {};
		const message = firstChoice.message as Record<string, unknown> | undefined;
		const usage = (data.usage as Record<string, unknown>) ?? {};

		return {
			exitCode: 0,
			output: (message?.content as string) ?? "",
			events: [],
			filesChanged: [],
			usage: {
				promptTokens: usage.prompt_tokens ?? 0,
				completionTokens: usage.completion_tokens ?? 0,
				totalTokens: usage.total_tokens ?? 0,
			},
			agentId: this.agent,
		};
	}
}
