import type { ILLMProvider } from "../../../src/domain/ports.js";

/**
 * Vercel AI SDK adapter implementing ILLMProvider.
 *
 * Uses Vercel AI SDK's `generateText()` and `streamText()` for multi-provider
 * LLM access (OpenAI, Anthropic, Google, etc.).
 *
 * Model strings follow the `provider:model` format (e.g., `openai:gpt-4o`).
 * API keys are resolved from environment variables.
 */
export class VercelAIAdapter implements ILLMProvider {
	async complete(
		model: string,
		messages: Array<{ role: string; content: string }>,
		options?: Record<string, unknown>,
	): Promise<{ content: string; [key: string]: unknown }> {
		// Dynamic import to avoid requiring the dependency at module load time
		const { generateText } = await import("ai");
		const providerModel = await this.resolveModel(model);

		const result = await generateText({
			model: providerModel,
			messages: messages.map((m) => ({
				role: m.role as "system" | "user" | "assistant",
				content: m.content,
			})),
			temperature: options?.temperature as number | undefined,
			maxTokens: options?.max_tokens as number | undefined,
		});

		return {
			content: result.text,
			usage: result.usage,
			finishReason: result.finishReason,
		};
	}

	async *stream(
		model: string,
		messages: Array<{ role: string; content: string }>,
		options?: Record<string, unknown>,
	): AsyncGenerator<string, void, void> {
		const { streamText } = await import("ai");
		const providerModel = await this.resolveModel(model);

		const result = streamText({
			model: providerModel,
			messages: messages.map((m) => ({
				role: m.role as "system" | "user" | "assistant",
				content: m.content,
			})),
			temperature: options?.temperature as number | undefined,
			maxTokens: options?.max_tokens as number | undefined,
		});

		for await (const chunk of (await result).textStream) {
			yield chunk;
		}
	}

	private async resolveModel(modelString: string): Promise<unknown> {
		// Model format: "provider:model-name" (e.g., "openai:gpt-4o")
		// or just "model-name" (defaults to openai)
		const colonIdx = modelString.indexOf(":");
		let providerName: string;
		let modelName: string;

		if (colonIdx > 0) {
			providerName = modelString.slice(0, colonIdx);
			modelName = modelString.slice(colonIdx + 1);
		} else {
			providerName = "openai";
			modelName = modelString;
		}

		switch (providerName) {
			case "openai": {
				const { openai } = await import("@ai-sdk/openai");
				return openai(modelName);
			}
			case "anthropic": {
				const { anthropic } = await import("@ai-sdk/anthropic");
				return anthropic(modelName);
			}
			case "google": {
				const { google } = await import("@ai-sdk/google");
				return google(modelName);
			}
			default: {
				// Try openai as default provider
				const { openai } = await import("@ai-sdk/openai");
				return openai(modelString);
			}
		}
	}
}
