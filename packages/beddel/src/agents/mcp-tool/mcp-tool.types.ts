/**
 * MCP Tool Agent Types - Shared between client and server
 */

/**
 * Parameters for MCP tool invocation
 */
export interface McpToolHandlerParams {
  server_url: string;
  tool_name: string;
  tool_arguments?: Record<string, unknown>;
}

/**
 * Result from MCP tool invocation
 */
export interface McpToolHandlerResult {
  success: boolean;
  data?: string;
  tool_names?: string[];
  error?: string;
}

/**
 * MCP Tool agent metadata
 */
export interface McpToolMetadata {
  id: 'mcp-tool';
  name: string;
  description: string;
  category: 'integration';
  route: '/agents/mcp-tool';
}
