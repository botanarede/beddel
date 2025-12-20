/**
 * GitMCP Agent Types - Shared between client and server
 */

/**
 * Parameters for GitMCP documentation fetching
 */
export interface GitMcpHandlerParams {
  gitmcp_url: string;
}

/**
 * Result from GitMCP documentation fetching
 */
export interface GitMcpHandlerResult {
  success: boolean;
  chunks?: string[];
  source?: string;
  error?: string;
}

/**
 * GitMCP agent metadata
 */
export interface GitMcpMetadata {
  id: 'gitmcp';
  name: string;
  description: string;
  category: 'integration';
  route: '/agents/gitmcp';
  provides_knowledge: boolean;
  tags: string[];
}
