/**
 * Client Types - Safe type re-exports for client-side usage
 * These types contain no sensitive data or server-only logic
 */

// Re-export all shared types
export type {
  AgentMetadata,
  AgentResponse,
  ExecutionStep,
  WorkflowStepType,
  AgentCategory,
} from '../shared/types/agent.types';

export type {
  ExecutionResult,
  ExecutionStatus,
  ExecutionSummary,
  ExecutionLogEntry,
} from '../shared/types/execution.types';

export type {
  SchemaProperty,
  AgentSchemaDefinition,
  ValidationResult,
  ValidationError,
} from '../shared/types/schema.types';

// Agent-specific type exports (client-safe)
export type { JokerInput, JokerOutput, JokeHandlerParams, JokeHandlerResult } from '../agents/joker';
export type { TranslatorInput, TranslatorOutput, TranslationHandlerParams, TranslationHandlerResult } from '../agents/translator';
export type { ImageInput, ImageOutput, ImageStyle, ImageHandlerParams, ImageHandlerResult } from '../agents/image';
export type { McpToolInput, McpToolOutput, McpToolHandlerParams, McpToolHandlerResult } from '../agents/mcp-tool';
export type { GeminiVectorizeInput, GeminiVectorizeOutput, VectorizeHandlerParams, VectorizeHandlerResult } from '../agents/gemini-vectorize';
export type { ChromaDBInput, ChromaDBOutput, ChromaDBHandlerParams, ChromaDBHandlerResult, ChromaDBSearchResult } from '../agents/chromadb';
export type { GitMcpInput, GitMcpOutput, GitMcpHandlerParams, GitMcpHandlerResult } from '../agents/gitmcp';
export type { RagInput, RagOutput, RagHandlerParams, RagHandlerResult, ConversationMessage } from '../agents/rag';
export type { ChatInput, ChatOutput, ChatHandlerParams, ChatHandlerResult } from '../agents/chat';
