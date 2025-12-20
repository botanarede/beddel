import 'server-only';

/**
 * MCP Tool Agent Handler - Server-only execution logic
 * Generic agent for calling MCP server tools via SSE transport
 */

import type { ExecutionContext } from '../../types/executionContext';
import type { McpToolHandlerParams, McpToolHandlerResult } from './mcp-tool.types';

// MCP imports (lazy loaded to avoid issues if not installed)
let mcpClient: any = null;
let mcpSSETransport: any = null;

/**
 * Execute MCP tool invocation
 */
export async function executeMcpToolHandler(
  params: McpToolHandlerParams,
  _props: Record<string, string>,
  context: ExecutionContext
): Promise<McpToolHandlerResult> {
  const serverUrl = params.server_url;
  const toolName = params.tool_name;
  const toolArguments = params.tool_arguments || {};

  if (!serverUrl) {
    throw new Error('Missing required MCP input: server_url');
  }
  if (!toolName) {
    throw new Error('Missing required MCP input: tool_name');
  }

  context.log(`[MCP Tool] Connecting to ${serverUrl}...`);
  context.log(`[MCP Tool] Tool: ${toolName}`);

  try {
    // Lazy load MCP SDK
    if (!mcpClient) {
      const { Client } = await import('@modelcontextprotocol/sdk/client/index.js');
      const { SSEClientTransport } = await import('@modelcontextprotocol/sdk/client/sse.js');
      mcpClient = Client;
      mcpSSETransport = SSEClientTransport;

      // Setup EventSource for Node.js
      const eventsourceModule = await import('eventsource');
      const EventSourceClass = eventsourceModule.default || eventsourceModule;
      if (!(global as any).EventSource) {
        (global as any).EventSource = EventSourceClass;
      }
    }

    const transport = new mcpSSETransport(new URL(serverUrl));
    const client = new mcpClient(
      { name: 'beddel-mcp-client', version: '1.0.0' },
      { capabilities: {} }
    );

    await client.connect(transport);
    context.log('[MCP Tool] Connected!');

    // List available tools
    const tools = await client.listTools();
    const availableToolNames = tools.tools.map((t: any) => t.name);
    context.log(`[MCP Tool] Available tools: ${availableToolNames.join(', ')}`);

    // Handle list_tools special case
    if (toolName === 'list_tools') {
      await client.close();
      return {
        success: true,
        data: JSON.stringify(tools.tools),
        tool_names: availableToolNames,
      };
    }

    // Validate tool exists
    if (!availableToolNames.includes(toolName)) {
      await client.close();
      return {
        success: false,
        error: `Tool '${toolName}' not found. Available tools: ${availableToolNames.join(', ')}`,
      };
    }

    // Call the tool with timeout
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('MCP Tool Timeout (30s)')), 30000)
    );

    const callPromise = client.callTool({
      name: toolName,
      arguments: toolArguments,
    });

    const callResult: any = await Promise.race([callPromise, timeoutPromise]);
    await client.close();

    // Parse result content
    const textContent = callResult.content
      .filter((c: any) => c.type === 'text')
      .map((c: any) => c.text)
      .join('\n') || 'No text content returned';

    return { success: true, data: textContent };

  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    context.log(`[MCP Tool] Error: ${message}`);
    return { success: false, error: message };
  }
}
