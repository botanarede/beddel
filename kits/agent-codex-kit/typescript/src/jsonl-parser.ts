import { AdapterError } from "../../../src/domain/errors.js";

export interface CodexEvent {
	type: string;
	data?: Record<string, unknown>;
}

const KNOWN_EVENT_TYPES = new Set([
	"thread.started",
	"item.completed",
	"turn.completed",
]);

/**
 * Parse a single JSONL line into a CodexEvent.
 * Unknown event types are returned with a warning flag (forward-compatible).
 */
export function parseJsonlLine(line: string, lineNumber: number): CodexEvent | null {
	const trimmed = line.trim();
	if (!trimmed) return null;

	let parsed: Record<string, unknown>;
	try {
		parsed = JSON.parse(trimmed) as Record<string, unknown>;
	} catch {
		throw new AdapterError(
			"BEDDEL-ADAPT-538",
			`Malformed JSONL at line ${lineNumber}`,
			{ lineNumber, rawLine: trimmed.slice(0, 200) },
		);
	}

	const eventType = parsed.type as string | undefined;
	if (!eventType) {
		return { type: "unknown", data: parsed };
	}

	if (!KNOWN_EVENT_TYPES.has(eventType)) {
		return { type: eventType, data: parsed };
	}

	return { type: eventType, data: parsed };
}
