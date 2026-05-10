import type { ITracer } from "../../../src/domain/ports.js";

/**
 * OpenTelemetry-based tracer implementing the ITracer port.
 *
 * Uses `@opentelemetry/api` for span creation and management.
 * Requires OTel SDK initialization (NodeSDK) in the host application.
 *
 * @example
 * ```ts
 * import { OTelTracer } from '@beddel/observability-otel';
 * const tracer = new OTelTracer('beddel-workflow');
 * ```
 */
export class OTelTracer implements ITracer<unknown> {
	private tracerName: string;

	constructor(tracerName = "beddel") {
		this.tracerName = tracerName;
	}

	startSpan(name: string, attributes?: Record<string, unknown>): unknown {
		try {
			// Dynamic import to avoid hard dependency at module load time
			const api = requireOTelApi();
			if (!api) return null;

			const tracer = api.trace.getTracer(this.tracerName);
			const span = tracer.startSpan(name);

			if (attributes) {
				for (const [key, value] of Object.entries(attributes)) {
					if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
						span.setAttribute(key, value);
					} else {
						span.setAttribute(key, JSON.stringify(value));
					}
				}
			}

			return span;
		} catch {
			return null;
		}
	}

	endSpan(span: unknown, attributes?: Record<string, unknown>): void {
		try {
			if (!span || typeof span !== "object") return;
			const s = span as { setAttribute: (k: string, v: unknown) => void; end: () => void };

			if (attributes) {
				for (const [key, value] of Object.entries(attributes)) {
					if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
						s.setAttribute(key, value);
					} else {
						s.setAttribute(key, JSON.stringify(value));
					}
				}
			}

			s.end();
		} catch {
			// Silently ignore — tracing must never break the workflow
		}
	}

	recordException(span: unknown, error: Error): void {
		try {
			if (!span || typeof span !== "object") return;
			const s = span as { recordException: (e: Error) => void };
			s.recordException(error);
		} catch {
			// Silently ignore
		}
	}

	addAttribute(span: unknown, key: string, value: unknown): void {
		try {
			if (!span || typeof span !== "object") return;
			const s = span as { setAttribute: (k: string, v: unknown) => void };
			if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
				s.setAttribute(key, value);
			} else {
				s.setAttribute(key, JSON.stringify(value));
			}
		} catch {
			// Silently ignore
		}
	}
}

function requireOTelApi(): { trace: { getTracer: (name: string) => { startSpan: (name: string) => unknown } } } | null {
	try {
		// Use require() for synchronous lazy load — dynamic import() cannot be used here
		// because startSpan() is synchronous per the ITracer port contract and making it
		// async would cascade breaking changes to the interface. The require() call is
		// intentional and safe: @opentelemetry/api is an optional peer dependency.
		// eslint-disable-next-line @typescript-eslint/no-require-imports
		return require("@opentelemetry/api");
	} catch {
		return null;
	}
}
