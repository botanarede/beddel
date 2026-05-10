import { AdapterError } from "../../../src/domain/errors.js";
import type { ITracer } from "../../../src/domain/ports.js";

export interface LangfuseTracerConfig {
	publicKey?: string;
	secretKey?: string;
	baseUrl?: string;
	flushOnShutdown?: boolean;
}

export interface LangfuseSpanLike {
	id: string;
	traceId: string;
	name: string;
	startTime: Date;
	endTime?: Date;
	attributes: Record<string, unknown>;
	error?: Error;
}

export interface LangfuseClient {
	trace(params: Record<string, unknown>): { id: string; span(params: Record<string, unknown>): LangfuseSpanHandle };
	shutdownAsync(): Promise<void>;
}

export interface LangfuseSpanHandle {
	id: string;
	update(params: Record<string, unknown>): void;
	end(params?: Record<string, unknown>): void;
}

/**
 * Langfuse-backed tracer implementing the `ITracer` port.
 *
 * Gracefully degrades: all methods catch exceptions silently so that tracing
 * never breaks the workflow. Uses `langfuse@^3`.
 *
 * @implements {ITracer<LangfuseSpanLike>}
 */
export class LangfuseTracerAdapter implements ITracer<LangfuseSpanLike> {
	private readonly publicKey: string;
	private readonly secretKey: string;
	private readonly baseUrl: string;
	private readonly flushOnShutdown: boolean;
	private client: LangfuseClient | null = null;
	private currentTrace: { id: string; span(params: Record<string, unknown>): LangfuseSpanHandle } | null = null;
	private spanHandles = new Map<string, LangfuseSpanHandle>();

	constructor(config: LangfuseTracerConfig = {}) {
		this.publicKey = config.publicKey ?? process.env.LANGFUSE_PUBLIC_KEY ?? "";
		this.secretKey = config.secretKey ?? process.env.LANGFUSE_SECRET_KEY ?? "";
		this.baseUrl = config.baseUrl ?? process.env.LANGFUSE_BASE_URL ?? "https://cloud.langfuse.com";
		this.flushOnShutdown = config.flushOnShutdown ?? true;
	}

	/**
	 * Inject a pre-constructed Langfuse client (for testing).
	 */
	setClient(client: LangfuseClient): void {
		this.client = client;
	}

	private async getClient(): Promise<LangfuseClient | null> {
		if (this.client) return this.client;

		if (!this.publicKey || !this.secretKey) {
			return null;
		}

		try {
			const { Langfuse } = await import("langfuse");
			this.client = new Langfuse({
				publicKey: this.publicKey,
				secretKey: this.secretKey,
				baseUrl: this.baseUrl,
			}) as unknown as LangfuseClient;
			return this.client;
		} catch {
			return null;
		}
	}

	startSpan(name: string, attributes?: Record<string, unknown>): LangfuseSpanLike {
		const spanLike: LangfuseSpanLike = {
			id: this.generateId(),
			traceId: this.currentTrace?.id ?? this.generateId(),
			name,
			startTime: new Date(),
			attributes: attributes ?? {},
		};

		try {
			const client = this.client;
			if (!client) {
				this.getClient().catch(() => {});
				return spanLike;
			}

			if (!this.currentTrace) {
				this.currentTrace = client.trace({
					name: `beddel:${name}`,
					metadata: attributes,
				});
				spanLike.traceId = this.currentTrace.id;
			}

			const handle = this.currentTrace.span({
				name,
				metadata: attributes,
				startTime: spanLike.startTime,
			});

			spanLike.id = handle.id;
			this.spanHandles.set(handle.id, handle);
		} catch {
			// Graceful degradation — tracing never breaks the workflow
		}

		return spanLike;
	}

	endSpan(span: LangfuseSpanLike, attributes?: Record<string, unknown>): void {
		try {
			span.endTime = new Date();

			if (attributes) {
				Object.assign(span.attributes, attributes);
			}

			const handle = this.spanHandles.get(span.id);
			if (handle) {
				handle.end({
					metadata: { ...span.attributes, ...attributes },
					endTime: span.endTime,
				});
				this.spanHandles.delete(span.id);
			}
		} catch {
			// Graceful degradation
		}
	}

	recordException(span: LangfuseSpanLike, error: Error): void {
		try {
			span.error = error;

			const handle = this.spanHandles.get(span.id);
			if (handle) {
				handle.update({
					level: "ERROR",
					statusMessage: error.message,
					metadata: {
						...span.attributes,
						"error.type": error.name,
						"error.message": error.message,
						"error.stack": error.stack,
					},
				});
			}
		} catch {
			// Graceful degradation
		}
	}

	addAttribute(span: LangfuseSpanLike, key: string, value: unknown): void {
		try {
			span.attributes[key] = value;

			const handle = this.spanHandles.get(span.id);
			if (handle) {
				handle.update({
					metadata: { ...span.attributes, [key]: value },
				});
			}
		} catch {
			// Graceful degradation
		}
	}

	/**
	 * Flush and shut down the Langfuse client. Call at workflow end.
	 */
	async shutdown(): Promise<void> {
		if (!this.flushOnShutdown || !this.client) return;

		try {
			await this.client.shutdownAsync();
		} catch (error) {
			throw new AdapterError(
				"BEDDEL-ADAPT-544",
				`Langfuse shutdown failed: ${error instanceof Error ? error.message : String(error)}`,
			);
		} finally {
			this.currentTrace = null;
			this.spanHandles.clear();
		}
	}

	private generateId(): string {
		return `lf-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
	}
}
