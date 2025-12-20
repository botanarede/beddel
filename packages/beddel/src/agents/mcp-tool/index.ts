/**
 * MCP Tool Agent - Public exports (client-safe)
 */

// Schema exports (client-safe)
export { McpToolInputSchema, McpToolOutputSchema } from './mcp-tool.schema';
export type { McpToolInput, McpToolOutput } from './mcp-tool.schema';

// Type exports (client-safe)
export type { McpToolHandlerParams, McpToolHandlerResult, McpToolMetadata } from './mcp-tool.types';

// Metadata (client-safe)
export const mcpToolMetadata = {
  id: 'mcp-tool',
  name: 'MCP Tool Agent',
  description: 'Generic agent for calling MCP server tools via SSE transport',
  category: 'integration',
  route: '/agents/mcp-tool',
} as const;
