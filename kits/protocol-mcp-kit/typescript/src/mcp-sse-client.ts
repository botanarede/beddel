/**
 * MCPSSEClient — IMCPClient adapter using @modelcontextprotocol/sdk SSE/HTTP transport.
 * AD-2: Uses official MCP SDK, not home-rolled protocol.
 *
 * Connects to MCP servers over SSE (Server-Sent Events) or streamable HTTP.
 * NOTE: Kit boundary — this file is NOT part of the core build.
 */

import type { IMCPClient, ToolDescriptor } from "@beddel/core";

export class MCPSSEClient implements IMCPClient {
	private client: unknown = null;
	private transport: unknown = null;
	private connected = false;

	async connect(serverUri: string): Promise<void> {
		const { Client } = await import("@modelcontextprotocol/sdk/client/index.js");
		const { SSEClientTransport } = await import(
			"@modelcontextprotocol/sdk/client/sse.js"
		);

		const url = new URL(serverUri);
		const transport = new SSEClientTransport(url);

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
