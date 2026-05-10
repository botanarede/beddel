/**
 * MCPStdioClient — IMCPClient adapter using @modelcontextprotocol/sdk stdio transport.
 * AD-2: Uses official MCP SDK, not home-rolled protocol.
 *
 * This adapter connects to MCP servers via stdio (subprocess) transport.
 * It delegates to the SDK's Client and StdioClientTransport classes.
 *
 * NOTE: Kit boundary — this file is NOT part of the core build.
 * The SDK dependency stays outside the core dependency graph.
 */

// Type-only import for the port contract
import type { IMCPClient, ToolDescriptor } from "@beddel/core";

export interface MCPStdioClientOptions {
	command: string;
	args?: string[];
	env?: Record<string, string>;
}

export class MCPStdioClient implements IMCPClient {
	private client: unknown = null;
	private transport: unknown = null;
	private connected = false;

	constructor(private readonly options: MCPStdioClientOptions) {}

	async connect(serverUri: string): Promise<void> {
		// Dynamic import — only resolve SDK at runtime in the kit context
		const { Client } = await import("@modelcontextprotocol/sdk/client/index.js");
		const { StdioClientTransport } = await import(
			"@modelcontextprotocol/sdk/client/stdio.js"
		);

		const transport = new StdioClientTransport({
			command: this.options.command,
			args: this.options.args,
			env: this.options.env,
		});

		const client = new Client({ name: "beddel-mcp", version: "0.1.0" }, {});
		await client.connect(transport);

		this.client = client;
		this.transport = transport;
		this.connected = true;
	}

	async listTools(): Promise<ToolDescriptor[]> {
		if (!this.connected || !this.client) {
			throw new Error("Not connected. Call connect() first.");
		}
		const client = this.client as { listTools(): Promise<{ tools: ToolDescriptor[] }> };
		const result = await client.listTools();
		return result.tools;
	}

	async callTool(name: string, args: Record<string, unknown>): Promise<unknown> {
		if (!this.connected || !this.client) {
			throw new Error("Not connected. Call connect() first.");
		}
		const client = this.client as {
			callTool(params: {
				name: string;
				arguments: Record<string, unknown>;
			}): Promise<unknown>;
		};
		return client.callTool({ name, arguments: args });
	}

	async disconnect(): Promise<void> {
		if (!this.connected) return;
		const client = this.client as { close?(): Promise<void> } | null;
		await client?.close?.();
		this.client = null;
		this.transport = null;
		this.connected = false;
	}
}
