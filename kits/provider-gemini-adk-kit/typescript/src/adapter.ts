import type { ILLMProvider } from "../../../src/domain/ports.js";

/**
 * Google Gemini ADK direct adapter implementing ILLMProvider.
 *
 * Uses `@google/generative-ai` for direct Gemini API access.
 * API key is read from `GEMINI_API_KEY` or `GOOGLE_API_KEY` env vars.
 *
 * @example
 * ```ts
 * const adapter = new GeminiADKAdapter();
 * const result = await adapter.complete("gemini-2.0-flash", [
 *   { role: "user", content: "Hello!" }
 * ]);
 * ```
 */
export class GeminiADKAdapter implements ILLMProvider {
	private apiKey: string;

	constructor(apiKey?: string) {
		this.apiKey =
			apiKey ?? process.env.GEMINI_API_KEY ?? process.env.GOOGLE_API_KEY ?? "";
	}

	async complete(
		model: string,
		messages: Array<{ role: string; content: string }>,
		options?: Record<string, unknown>,
	): Promise<{ content: string; [key: string]: unknown }> {
		const { GoogleGenerativeAI } = await import("@google/generative-ai");
		const genAI = new GoogleGenerativeAI(this.apiKey);

		const geminiModel = genAI.getGenerativeModel({
			model: this.normalizeModelName(model),
			generationConfig: {
				temperature: options?.temperature as number | undefined,
				maxOutputTokens: options?.max_tokens as number | undefined,
			},
		});

		const systemMessages = messages.filter((m) => m.role === "system");
		const chatMessages = messages.filter((m) => m.role !== "system");

		const history = chatMessages.slice(0, -1).map((m) => ({
			role: m.role === "assistant" ? "model" : "user",
			parts: [{ text: m.content }],
		}));

		const lastMessage = chatMessages[chatMessages.length - 1];

		const chat = geminiModel.startChat({
			history,
			systemInstruction: systemMessages.length > 0
				? { role: "user", parts: [{ text: systemMessages.map((m) => m.content).join("\n") }] }
				: undefined,
		});

		const result = await chat.sendMessage(lastMessage?.content ?? "");
		const response = result.response;

		return {
			content: response.text(),
			usage: response.usageMetadata
				? {
						promptTokens: response.usageMetadata.promptTokenCount,
						completionTokens: response.usageMetadata.candidatesTokenCount,
						totalTokens: response.usageMetadata.totalTokenCount,
					}
				: {},
		};
	}

	async *stream(
		model: string,
		messages: Array<{ role: string; content: string }>,
		options?: Record<string, unknown>,
	): AsyncGenerator<string, void, void> {
		const { GoogleGenerativeAI } = await import("@google/generative-ai");
		const genAI = new GoogleGenerativeAI(this.apiKey);

		const geminiModel = genAI.getGenerativeModel({
			model: this.normalizeModelName(model),
			generationConfig: {
				temperature: options?.temperature as number | undefined,
				maxOutputTokens: options?.max_tokens as number | undefined,
			},
		});

		const chatMessages = messages.filter((m) => m.role !== "system");
		const lastMessage = chatMessages[chatMessages.length - 1];

		const result = await geminiModel.generateContentStream(lastMessage?.content ?? "");
		for await (const chunk of result.stream) {
			const text = chunk.text();
			if (text) yield text;
		}
	}

	private normalizeModelName(model: string): string {
		// Strip provider prefix if present (e.g., "google:gemini-2.0-flash" → "gemini-2.0-flash")
		if (model.startsWith("google:")) return model.slice(7);
		if (model.startsWith("gemini:")) return model.slice(7);
		return model;
	}
}
