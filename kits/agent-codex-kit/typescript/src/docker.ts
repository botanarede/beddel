/**
 * Docker command builder for Codex container execution.
 */
export interface DockerRunOptions {
	image: string;
	apiKey: string;
	model: string;
	sandbox: string;
	timeoutMs: number;
	repoPath?: string;
	networkPolicy?: string;
}

const SANDBOX_MOUNT_MODES: Record<string, string> = {
	"read-only": "ro",
	"workspace-write": "rw",
	"danger-full-access": "rw",
};

export function buildDockerArgs(options: DockerRunOptions): string[] {
	const args = ["run", "--rm", "-i"];

	args.push("-e", `OPENAI_API_KEY=${options.apiKey}`);
	args.push("-e", `CODEX_MODEL=${options.model}`);

	if (options.repoPath) {
		const mountMode = SANDBOX_MOUNT_MODES[options.sandbox] ?? "ro";
		args.push("-v", `${options.repoPath}:/workspace:${mountMode}`);
		args.push("-w", "/workspace");
	}

	if (options.sandbox === "danger-full-access") {
		args.push("--privileged");
	} else {
		args.push("--network=none");
	}

	args.push(options.image);
	args.push("codex", "exec", "--json", "--full-auto");

	return args;
}
