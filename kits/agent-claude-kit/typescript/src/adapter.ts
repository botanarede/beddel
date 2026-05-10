import { AdapterError } from "../../../src/domain/errors.js";
import type { AgentResult, IAgentAdapter } from "../../../src/domain/ports.js";

export interface ClaudeAdapterConfig {
	model?: string;
	apiKey?: string;
	maxTurns?: number;
	timeoutMs?: number;
	fileMutationTools?: string[];
}

interface AnthropicMessage {
	role: string;
	content: string | AnthropicContentBlock[];
}

interface AnthropicContentBlock {
	type: string;
	text?: string;
	id?: string;
	name?: string;
	input?: Record<string, unknown>;
}

interface AnthropicResponse {
	id: string;
	content: AnthropicContentBlock[];
	stop_reason: string | null;
	usage: { input_tokens: number; output_tokens: number };
}

interface AnthropicTool {
	name: string;
	description: string;
	input_schema: Record<string, unknown>;
}

interface AnthropicStreamEvent {
	type: string;
	delta?: { type?: string; text?: string };
	content_block?: AnthropicContentBlock;
	message?: AnthropicResponse;
	index?: number;
}

export interface AnthropicClient {
	messages: {
		create(params: Record<string, unknown>): Promise<AnthropicResponse>;
		stream(params: Record<string, unknown>): AsyncIterable<AnthropicStreamEvent>;
	};
}

const FILE_MUTATION_TOOLS_DEFAULT = ["write_file", "edit_file", "create_file"];

/**
 * Claude agent adapter via `@anthropic-ai/sdk`.
 *
 * Composes the Anthropic Messages API directly (per AD-1). Tool-use loop is
 * internal, bounded by `maxTurns`.
 *
 * @implements {IAgentAdapter}
 */
export class ClaudeAgentAdapter implements IAgentAdapter {
	private readonly model: string;
	private readonly apiKey: string;
	private readonly maxTurns: number;
	private readonly timeoutMs: number;
	private readonly fileMutationTools: string[];
	private client: AnthropicClient | null = null;

	constructor(config: ClaudeAdapterConfig = {}) {
		this.model = config.model ?? "claude-sonnet-4";
		this.apiKey = config.apiKey ?? process.env.ANTHROPIC_API_KEY ?? "";
		this.maxTurns = config.maxTurns ?? 25;
		this.timeoutMs = config.timeoutMs ?? 300_000;
		this.fileMutationTools = config.fileMutationTools ?? FILE_MUTATION_TOOLS_DEFAULT;

		if (!this.apiKey) {
			throw new AdapterError(
				"BEDDEL-ADAPT-507",
				"No API key — set ANTHROPIC_API_KEY or pass apiKey in constructor",
			);
		}
	}

	/**
	 * Inject a pre-constructed Anthropic client (for testing).
	 */
	setClient(client: AnthropicClient): void {
		this.client = client;
	}

	private async getClient(): Promise<AnthropicClient> {
		if (this.client) return this.client;
		const { default: Anthropic } = await import("@anthropic-ai/sdk");
		this.client = new Anthropic({ apiKey: this.apiKey }) as unknown as AnthropicClient;
		return this.client;
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
		const client = await this.getClient();
		const model = options?.model ?? this.model;
		const sandbox = options?.sandbox ?? "read-only";
		const messages: AnthropicMessage[] = [{ role: "user", content: prompt }];
		const anthropicTools = this.buildTools(options?.tools, options?.outputSchema, sandbox);
		const filesChanged: string[] = [];

		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

		try {
			for (let turn = 0; turn <= this.maxTurns; turn++) {
				const params: Record<string, unknown> = {
					model,
					max_tokens: 4096,
					messages,
				};
				if (anthropicTools.length > 0) params.tools = anthropicTools;

				let response: AnthropicResponse;
				try {
					response = await client.messages.create(params);
				} catch (error) {
					if (controller.signal.aborted) {
						throw new AdapterError(
							"BEDDEL-ADAPT-509",
							`Claude request timed out after ${this.timeoutMs}ms`,
							{ timeoutMs: this.timeoutMs },
						);
					}
					this.handleApiError(error);
					throw error;
				}

				const textBlocks = response.content.filter((b) => b.type === "text");
				const toolUseBlocks = response.content.filter((b) => b.type === "tool_use");

				if (options?.outputSchema) {
					const schemaToolResult = response.content.find(
						(b) => b.type === "tool_use" && b.name === "respond_with_schema",
					);
					if (schemaToolResult?.input) {
						return this.buildResult(
							JSON.stringify(schemaToolResult.input),
							response.usage,
							filesChanged,
						);
					}
				}

				if (toolUseBlocks.length === 0 || response.stop_reason === "end_turn") {
					const outputText = textBlocks.map((b) => b.text ?? "").join("");
					return this.buildResult(outputText, response.usage, filesChanged);
				}

				if (turn === this.maxTurns) {
					throw new AdapterError(
						"BEDDEL-ADAPT-505",
						`Tool-use cycle exceeded maxTurns (${this.maxTurns})`,
						{ maxTurns: this.maxTurns },
					);
				}

				messages.push({ role: "assistant", content: response.content });

				const toolResults: AnthropicContentBlock[] = [];
				for (const block of toolUseBlocks) {
					if (this.fileMutationTools.includes(block.name ?? "")) {
						const path = (block.input as Record<string, unknown>)?.path as string | undefined;
						if (path) filesChanged.push(path);
					}

					toolResults.push({
						type: "tool_result",
						id: block.id,
						text: JSON.stringify({ status: "ok" }),
					});
				}

				messages.push({ role: "user", content: toolResults });
			}

			throw new AdapterError(
				"BEDDEL-ADAPT-505",
				`Tool-use cycle exceeded maxTurns (${this.maxTurns})`,
				{ maxTurns: this.maxTurns },
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
		const client = await this.getClient();
		const model = options?.model ?? this.model;
		const sandbox = options?.sandbox ?? "read-only";
		const anthropicTools = this.buildTools(options?.tools, undefined, sandbox);

		const params: Record<string, unknown> = {
			model,
			max_tokens: 4096,
			messages: [{ role: "user", content: prompt }],
			stream: true,
		};
		if (anthropicTools.length > 0) params.tools = anthropicTools;

		try {
			const stream = client.messages.stream(params);

			for await (const event of stream) {
				if (event.type === "content_block_delta" && event.delta?.text) {
					yield { type: "content_block_delta", text: event.delta.text };
				} else if (event.type === "content_block_start" && event.content_block?.type === "tool_use") {
					yield {
						type: "tool_use",
						name: event.content_block.name,
						input: event.content_block.input,
					};
				} else if (event.type === "message_stop") {
					yield { type: "message_stop" };
				}
			}
		} catch (error) {
			if (error instanceof AdapterError) throw error;
			this.handleApiError(error);
			throw error;
		}
	}

	private buildTools(
		tools?: string[],
		outputSchema?: Record<string, unknown>,
		sandbox?: string,
	): AnthropicTool[] {
		const result: AnthropicTool[] = [];

		if (tools) {
			for (const name of tools) {
				const tool: AnthropicTool = {
					name,
					description: `Tool: ${name}`,
					input_schema: { type: "object", properties: {} },
				};

				if (sandbox === "read-only" && this.fileMutationTools.includes(name)) {
					continue;
				}

				result.push(tool);
			}
		}

		if (outputSchema) {
			result.push({
				name: "respond_with_schema",
				description: "Respond with structured output matching the given schema",
				input_schema: outputSchema,
			});
		}

		return result;
	}

	private handleApiError(error: unknown): never {
		if (error instanceof AdapterError) throw error;

		const err = error as { status?: number; headers?: Record<string, string>; message?: string };

		if (err.status === 429) {
			throw new AdapterError("BEDDEL-ADAPT-508", "Anthropic API rate limited (HTTP 429)", {
				retryAfter: err.headers?.["retry-after"],
			});
		}

		throw new AdapterError(
			"BEDDEL-ADAPT-509",
			`Anthropic API error: ${err.message ?? String(error)}`,
		);
	}

	private buildResult(
		output: string,
		usage: { input_tokens: number; output_tokens: number },
		filesChanged: string[],
	): AgentResult {
		return {
			exitCode: 0,
			output,
			events: [],
			filesChanged,
			usage: {
				promptTokens: usage.input_tokens,
				completionTokens: usage.output_tokens,
				totalTokens: usage.input_tokens + usage.output_tokens,
			},
			agentId: "claude",
		};
	}
}
