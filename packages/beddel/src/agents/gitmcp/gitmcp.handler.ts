import 'server-only';

/**
 * GitMCP Agent Handler - Server-only execution logic
 * Fetches and chunks GitHub repository documentation via gitmcp.io MCP servers
 */

import type { ExecutionContext } from '../../types/executionContext';
import type { GitMcpHandlerParams, GitMcpHandlerResult } from './gitmcp.types';
import { executeMcpToolHandler } from '../mcp-tool/mcp-tool.handler';

/**
 * Split text into chunks preserving paragraphs
 */
function splitIntoChunks(text: string, chunkSize: number): string[] {
  const paragraphs = text.split(/\n\s*\n/);
  const chunks: string[] = [];
  let currentChunk = '';

  for (const para of paragraphs) {
    if (currentChunk.length + para.length > chunkSize && currentChunk) {
      chunks.push(currentChunk.trim());
      currentChunk = para;
    } else {
      currentChunk += (currentChunk ? '\n\n' : '') + para;
    }
  }

  if (currentChunk) chunks.push(currentChunk.trim());
  return chunks;
}

/**
 * Execute GitMCP documentation fetching
 */
export async function executeGitMcpHandler(
  params: GitMcpHandlerParams,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<GitMcpHandlerResult> {
  const gitmcpUrl = params.gitmcp_url;

  if (!gitmcpUrl) {
    throw new Error('Missing required GitMCP input: gitmcp_url');
  }

  context.log(`[GitMCP] Fetching content from ${gitmcpUrl}...`);

  try {
    const sseUrl = `${gitmcpUrl}/sse`;

    // Use MCP tool to list available tools
    const toolListResult = await executeMcpToolHandler(
      {
        server_url: sseUrl,
        tool_name: 'list_tools',
        tool_arguments: {},
      },
      props,
      context
    );

    let selectedToolName = '';
    let selectedToolArgs: Record<string, unknown> = {};

    if (toolListResult?.success && toolListResult?.tool_names) {
      const availableTools = toolListResult.tool_names;
      context.log(`[GitMCP] Discovered tools: ${availableTools.join(', ')}`);

      // Heuristic tool selection
      if (availableTools.includes('fetch_beddel_alpha_documentation')) {
        selectedToolName = 'fetch_beddel_alpha_documentation';
        selectedToolArgs = { path: '/' };
      } else if (availableTools.includes('read_file')) {
        selectedToolName = 'read_file';
        selectedToolArgs = { path: 'README.md' };
      } else if (availableTools.includes('fetch_generic_url_content')) {
        selectedToolName = 'fetch_generic_url_content';
        selectedToolArgs = { url: gitmcpUrl };
      } else {
        selectedToolName = availableTools.find((t) => t !== 'list_tools' && !t.includes('search')) || availableTools[0];
        selectedToolArgs = { path: '/' };
      }
    } else {
      selectedToolName = 'fetch_beddel_alpha_documentation';
      selectedToolArgs = { path: '/' };
    }

    context.log(`[GitMCP] Selected tool: ${selectedToolName}`);

    // Fetch content
    const mcpResult = await executeMcpToolHandler(
      {
        server_url: sseUrl,
        tool_name: selectedToolName,
        tool_arguments: selectedToolArgs,
      },
      props,
      context
    );

    if (!mcpResult?.success) {
      throw new Error(`Failed to fetch docs via MCP: ${mcpResult?.error}`);
    }

    const textContent = mcpResult.data;
    if (!textContent) {
      throw new Error('No content returned from MCP tool');
    }

    // Chunking
    const chunks = splitIntoChunks(textContent, 800);
    context.log(`[GitMCP] Content split into ${chunks.length} chunks`);

    return { success: true, chunks, source: gitmcpUrl };

  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    context.log(`[GitMCP] Error: ${message}`);
    return { success: false, chunks: [], error: message };
  }
}
