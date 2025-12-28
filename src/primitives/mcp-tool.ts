/**
 * Beddel Protocol - MCP Tool Primitive
 * 
 * Connects to external MCP servers via SSE transport and executes tools.
 * Enables declarative agents to integrate with any MCP-compatible service
 * like GitMCP, Context7, and custom MCP servers.
 * 
 * Server-only: Uses @modelcontextprotocol/sdk which requires Node.js.
 */

import type { StepConfig, ExecutionContext, PrimitiveHandler } from '../types';
import { resolveVariables } from '../core/variable-resolver';

/**
 * MCP Tool step configuration from YAML.
 */
interface McpToolConfig extends StepConfig {
    /** MCP server URL (SSE endpoint) */
    url: string;
    /** Name of the tool to execute (use 'list_tools' to discover available tools) */
    tool: string;
    /** Arguments to pass to the tool */
    arguments?: Record<string, unknown>;
    /** Timeout in milliseconds (default: 30000) */
    timeout?: number;
}

/**
 * Result from MCP tool execution.
 */
interface McpToolResult {
    success: boolean;
    data?: string;
    toolNames?: string[];
    error?: string;
}

// Lazy-loaded MCP SDK components
let Client: any = null;
let SSEClientTransport: any = null;

/**
 * Lazy load MCP SDK to avoid issues if not installed.
 */
async function loadMcpSdk(): Promise<void> {
    if (Client && SSEClientTransport) return;

    try {
        const clientModule = await import('@modelcontextprotocol/sdk/client/index.js');
        const sseModule = await import('@modelcontextprotocol/sdk/client/sse.js');
        
        Client = clientModule.Client;
        SSEClientTransport = sseModule.SSEClientTransport;
    } catch (error) {
        throw new Error(
            '[Beddel] Failed to load @modelcontextprotocol/sdk. ' +
            'Make sure it is installed: npm install @modelcontextprotocol/sdk'
        );
    }
}


/**
 * MCP Tool Primitive Handler
 * 
 * Connects to an MCP server via SSE and executes the specified tool.
 * Supports tool discovery via the special 'list_tools' tool name.
 * 
 * @param config - Step configuration from YAML
 * @param context - Execution context with input and variables
 * @returns McpToolResult with success status and data or error
 */
export const mcpToolPrimitive: PrimitiveHandler = async (
    config: StepConfig,
    context: ExecutionContext
): Promise<Record<string, unknown>> => {
    const mcpConfig = config as McpToolConfig;

    // Resolve variables in config
    const url = resolveVariables(mcpConfig.url, context) as string;
    const toolName = resolveVariables(mcpConfig.tool, context) as string;
    const toolArguments = mcpConfig.arguments 
        ? resolveVariables(mcpConfig.arguments, context) as Record<string, unknown>
        : {};
    const timeout = mcpConfig.timeout || 30000;

    // Validate required fields
    if (!url) {
        return { success: false, error: 'Missing required config: url' };
    }
    if (!toolName) {
        return { success: false, error: 'Missing required config: tool' };
    }

    console.log(`[Beddel MCP] Connecting to ${url}...`);
    console.log(`[Beddel MCP] Tool: ${toolName}`);

    let client: any = null;

    try {
        // Lazy load MCP SDK
        await loadMcpSdk();

        // Create transport and client
        const transport = new SSEClientTransport(new URL(url));
        client = new Client(
            { name: 'beddel-mcp-client', version: '1.0.0' },
            { capabilities: {} }
        );

        // Connect with timeout
        const connectPromise = client.connect(transport);
        const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('MCP connection timeout')), timeout)
        );

        await Promise.race([connectPromise, timeoutPromise]);
        console.log('[Beddel MCP] Connected!');

        // List available tools
        const toolsResponse = await client.listTools();
        const availableTools = toolsResponse.tools || [];
        const toolNames = availableTools.map((t: any) => t.name);
        console.log(`[Beddel MCP] Available tools: ${toolNames.join(', ')}`);

        // Handle list_tools special case
        if (toolName === 'list_tools') {
            await client.close();
            return {
                success: true,
                data: JSON.stringify(availableTools, null, 2),
                toolNames,
            };
        }

        // Validate tool exists
        if (!toolNames.includes(toolName)) {
            await client.close();
            return {
                success: false,
                error: `Tool '${toolName}' not found. Available: ${toolNames.join(', ')}`,
                toolNames,
            };
        }

        // Call the tool with timeout
        const callPromise = client.callTool({
            name: toolName,
            arguments: toolArguments,
        });

        const callTimeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error(`MCP tool timeout (${timeout}ms)`)), timeout)
        );

        const result: any = await Promise.race([callPromise, callTimeoutPromise]);
        await client.close();

        // Extract text content from result
        const textContent = (result.content || [])
            .filter((c: any) => c.type === 'text')
            .map((c: any) => c.text)
            .join('\n') || 'No text content returned';

        console.log(`[Beddel MCP] Tool executed successfully`);

        return {
            success: true,
            data: textContent,
        };

    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        console.error(`[Beddel MCP] Error: ${message}`);

        // Ensure client is closed on error
        if (client) {
            try {
                await client.close();
            } catch {
                // Ignore close errors
            }
        }

        return {
            success: false,
            error: message,
        };
    }
};
