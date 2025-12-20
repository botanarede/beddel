/**
 * GitMCP Agent - Public exports (client-safe)
 */

// Schema exports (client-safe)
export { GitMcpInputSchema, GitMcpOutputSchema } from './gitmcp.schema';
export type { GitMcpInput, GitMcpOutput } from './gitmcp.schema';

// Type exports (client-safe)
export type { GitMcpHandlerParams, GitMcpHandlerResult, GitMcpMetadata } from './gitmcp.types';

// Metadata (client-safe)
export const gitmcpMetadata = {
  id: 'gitmcp',
  name: 'GitMCP Documentation Agent',
  description: 'Fetches and chunks GitHub repository documentation via gitmcp.io MCP servers',
  category: 'integration',
  route: '/agents/gitmcp',
  provides_knowledge: true,
  tags: ['gitmcp', 'documentation', 'github', 'mcp'],
} as const;
