import 'server-only';

/**
 * Workflow Executor - Server-only workflow step execution
 * Delegates to individual agent handlers based on step type
 */

import type { ExecutionContext } from '../types/executionContext';
import type { WorkflowStepType } from '../shared/types/agent.types';

// Import handlers from each agent
import { executeJokeHandler } from '../agents/joker/joker.handler';
import { executeTranslationHandler } from '../agents/translator/translator.handler';
import { executeImageHandler } from '../agents/image/image.handler';
import { executeMcpToolHandler } from '../agents/mcp-tool/mcp-tool.handler';
import { executeVectorizeHandler } from '../agents/gemini-vectorize/gemini-vectorize.handler';
import { executeChromaDBHandler } from '../agents/chromadb/chromadb.handler';
import { executeGitMcpHandler } from '../agents/gitmcp/gitmcp.handler';
import { executeRagHandler } from '../agents/rag/rag.handler';
import { executeChatHandler } from '../agents/chat/chat.handler';

/**
 * Handler function type - uses any for params to allow flexible handler signatures
 */
type HandlerFunction = (
  params: any,
  props: Record<string, string>,
  context: ExecutionContext
) => Promise<unknown>;

/**
 * Map of workflow step types to their handlers
 * Maps both legacy (Portuguese) and new (English) step type names
 */
const handlerMap: Record<string, HandlerFunction> = {
  // English step types (preferred)
  'joke': executeJokeHandler,
  'translation': executeTranslationHandler,
  'image': executeImageHandler,
  'mcp-tool': executeMcpToolHandler,
  'vectorize': executeVectorizeHandler,
  'chromadb': executeChromaDBHandler,
  'gitmcp': executeGitMcpHandler,
  'rag': executeRagHandler,
  'chat': executeChatHandler,
  // Legacy step types (for backward compatibility)
  'genkit-joke': executeJokeHandler,
  'genkit-translation': executeTranslationHandler,
  'genkit-image': executeImageHandler,
  'gemini-vectorize': executeVectorizeHandler,
};

/**
 * Execute a workflow step by delegating to the appropriate handler
 */
export async function executeWorkflowStep(
  stepType: WorkflowStepType | string,
  params: Record<string, unknown>,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<unknown> {
  const handler = handlerMap[stepType];
  if (!handler) {
    throw new Error(`Unknown workflow step type: ${stepType}`);
  }
  return handler(params, props, context);
}

/**
 * Get all available workflow step types
 */
export function getAvailableStepTypes(): string[] {
  return Object.keys(handlerMap);
}

/**
 * Check if a step type is supported
 */
export function isStepTypeSupported(stepType: string): boolean {
  return stepType in handlerMap;
}

// Export individual handlers for direct use
export {
  executeJokeHandler,
  executeTranslationHandler,
  executeImageHandler,
  executeMcpToolHandler,
  executeVectorizeHandler,
  executeChromaDBHandler,
  executeGitMcpHandler,
  executeRagHandler,
  executeChatHandler,
};
