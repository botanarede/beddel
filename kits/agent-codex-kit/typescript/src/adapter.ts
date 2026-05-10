import { type ChildProcess, spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { AdapterError } from "../../../src/domain/errors.js";
import type { AgentResult, IAgentAdapter } from "../../../src/domain/ports.js";
import { buildDockerArgs } from "./docker.js";
import { type CodexEvent, parseJsonlLine } from "./jsonl-parser.js";

export interface CodexAdapterConfig {
	apiKey?: string;
	model?: string;
	dockerImage?: string;
	timeoutMs?: number;
	repoPath?: string;
}

export interface SpawnFn {
	(command: string, args: string[]): ChildProcess;
}

/**
 * Codex agent adapter — Docker subprocess + JSONL parsing.
 *
 * Spawns `docker run --rm -i {image} codex exec --json --full-auto`
 * and parses JSONL events from stdout. Zero runtime dependencies beyond
 * `node:child_process` and `node:readline`.
 *
 * @implements {IAgentAdapter}
 */
export class CodexAgentAdapter implements IAgentAdapter {
	private readonly apiKey: string;
	private readonly model: string;
	private readonly dockerImage: string;
	private readonly timeoutMs: number;
	private readonly repoPath: string | undefined;
	private spawnFn: SpawnFn = spawn;

	constructor(config: CodexAdapterConfig = {}) {
		this.apiKey = config.apiKey ?? process.env.OPENAI_API_KEY ?? "";
		this.model = config.model ?? process.env.CODEX_MODEL ?? "gpt-5.3-codex";
		this.dockerImage =
			config.dockerImage ?? process.env.CODEX_DOCKER_IMAGE ?? "codex-universal:latest";
		this.timeoutMs = config.timeoutMs
			? config.timeoutMs
			: process.env.CODEX_TIMEOUT_MS
				? Number(process.env.CODEX_TIMEOUT_MS)
				: 300_000;
		this.repoPath = config.repoPath;
	}

	setSpawnFn(fn: SpawnFn): void {
		this.spawnFn = fn;
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
		const sandbox = options?.sandbox ?? "read-only";
		const events: CodexEvent[] = [];
		let output = "";
		let stderr = "";

		const args = buildDockerArgs({
			image: this.dockerImage,
			apiKey: this.apiKey,
			model: options?.model ?? this.model,
			sandbox,
			timeoutMs: this.timeoutMs,
			repoPath: this.repoPath,
		});

		const child = this.spawnProcess(args);
		const timer = setTimeout(() => {
			child.kill("SIGKILL");
		}, this.timeoutMs);

		try {
			child.stdin?.write(prompt);
			child.stdin?.end();

			const rl = createInterface({ input: child.stdout! });
			let lineNumber = 0;

			for await (const line of rl) {
				lineNumber++;
				const event = parseJsonlLine(line, lineNumber);
				if (event) {
					events.push(event);
					if (event.type === "item.completed") {
						const text = (event.data?.output as string) ?? "";
						if (text) output += text;
					}
				}
			}

			child.stderr?.on("data", (chunk: Buffer) => {
				stderr = (stderr + chunk.toString()).slice(-1000);
			});

			const exitCode = await new Promise<number>((resolve) => {
				if (child.exitCode !== null) {
					resolve(child.exitCode);
					return;
				}
				child.on("exit", (code) => resolve(code ?? 1));
			});

			if (exitCode === 137) {
				throw new AdapterError("BEDDEL-ADAPT-539", "Container OOM-killed (exit 137)", {
					exitCode,
				});
			}

			if (exitCode !== 0) {
				throw new AdapterError(
					"BEDDEL-ADAPT-535",
					`codex exec failed with exit code ${exitCode}`,
					{ exitCode, stderr: stderr.slice(0, 500) },
				);
			}

			return {
				exitCode: 0,
				output,
				events: events.map((e) => e.data ?? {}),
				filesChanged: [],
				usage: {},
				agentId: "codex",
			};
		} catch (error) {
			if (error instanceof AdapterError) throw error;

			const errMsg = error instanceof Error ? error.message : String(error);
			if (errMsg.includes("ENOENT") || errMsg.includes("spawn docker")) {
				throw new AdapterError(
					"BEDDEL-ADAPT-537",
					"Docker not available or image not pullable",
					{ dockerImage: this.dockerImage },
				);
			}
			throw new AdapterError(
				"BEDDEL-ADAPT-535",
				`Codex execution failed: ${errMsg}`,
			);
		} finally {
			clearTimeout(timer);
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

		const args = buildDockerArgs({
			image: this.dockerImage,
			apiKey: this.apiKey,
			model: options?.model ?? this.model,
			sandbox,
			timeoutMs: this.timeoutMs,
			repoPath: this.repoPath,
		});

		const child = this.spawnProcess(args);
		const timer = setTimeout(() => {
			child.kill("SIGKILL");
		}, this.timeoutMs);

		try {
			child.stdin?.write(prompt);
			child.stdin?.end();

			const rl = createInterface({ input: child.stdout! });
			let lineNumber = 0;

			for await (const line of rl) {
				lineNumber++;
				const event = parseJsonlLine(line, lineNumber);
				if (event) {
					yield event.data ?? { type: event.type };
				}
			}
		} catch (error) {
			if (error instanceof AdapterError) throw error;
			throw new AdapterError(
				"BEDDEL-ADAPT-535",
				`Codex stream failed: ${error instanceof Error ? error.message : String(error)}`,
			);
		} finally {
			clearTimeout(timer);
			child.kill();
		}
	}

	private spawnProcess(args: string[]): ChildProcess {
		try {
			return this.spawnFn("docker", args);
		} catch (error) {
			throw new AdapterError(
				"BEDDEL-ADAPT-537",
				`Failed to spawn Docker process: ${error instanceof Error ? error.message : String(error)}`,
				{ dockerImage: this.dockerImage },
			);
		}
	}
}
