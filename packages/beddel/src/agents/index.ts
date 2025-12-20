/**
 * Agents Module - Public exports
 *
 * This module provides the agent registry and agent metadata.
 * Handler implementations are server-only and should be imported directly
 * from their respective agent folders when needed.
 */

// Registry exports
export { AgentRegistry, agentRegistry } from './registry';
export type { AgentRegistration } from './registry';

// Agent metadata exports (client-safe)
export { jokerMetadata } from './joker';
export { translatorMetadata } from './translator';
export { imageMetadata } from './image';
export { mcpToolMetadata } from './mcp-tool';
export { geminiVectorizeMetadata } from './gemini-vectorize';
export { chromadbMetadata } from './chromadb';
export { gitmcpMetadata } from './gitmcp';
export { ragMetadata } from './rag';
export { chatMetadata } from './chat';

// Schema exports (client-safe)
export { JokerInputSchema, JokerOutputSchema } from './joker';
export { TranslatorInputSchema, TranslatorOutputSchema } from './translator';
export { ImageInputSchema, ImageOutputSchema } from './image';
export { McpToolInputSchema, McpToolOutputSchema } from './mcp-tool';
export { GeminiVectorizeInputSchema, GeminiVectorizeOutputSchema } from './gemini-vectorize';
export { ChromaDBInputSchema, ChromaDBOutputSchema } from './chromadb';
export { GitMcpInputSchema, GitMcpOutputSchema } from './gitmcp';
export { RagInputSchema, RagOutputSchema } from './rag';
export { ChatInputSchema, ChatOutputSchema } from './chat';

// Type exports (client-safe)
export type { JokerInput, JokerOutput, JokeHandlerParams, JokeHandlerResult } from './joker';
export type { TranslatorInput, TranslatorOutput, TranslationHandlerParams, TranslationHandlerResult } from './translator';
export type { ImageInput, ImageOutput, ImageStyle, ImageHandlerParams, ImageHandlerResult } from './image';
export type { McpToolInput, McpToolOutput, McpToolHandlerParams, McpToolHandlerResult } from './mcp-tool';
export type { GeminiVectorizeInput, GeminiVectorizeOutput, VectorizeHandlerParams, VectorizeHandlerResult } from './gemini-vectorize';
export type { ChromaDBInput, ChromaDBOutput, ChromaDBHandlerParams, ChromaDBHandlerResult, ChromaDBSearchResult } from './chromadb';
export type { GitMcpInput, GitMcpOutput, GitMcpHandlerParams, GitMcpHandlerResult } from './gitmcp';
export type { RagInput, RagOutput, RagHandlerParams, RagHandlerResult, ConversationMessage } from './rag';
export type { ChatInput, ChatOutput, ChatHandlerParams, ChatHandlerResult } from './chat';

/**
 * All agent metadata for UI display
 */
export const allAgentMetadata = [
  { id: 'joker', name: 'Joker Agent', description: 'Tells jokes using Gemini Flash', category: 'utility', route: '/agents/joker' },
  { id: 'translator', name: 'Translator Agent', description: 'Translates text between languages using Gemini Flash via Genkit', category: 'translation', route: '/agents/translator' },
  { id: 'image', name: 'Image Generator Agent', description: 'Generates images using Gemini Flash with curated styles', category: 'creative', route: '/agents/image' },
  { id: 'mcp-tool', name: 'MCP Tool Agent', description: 'Generic agent for calling MCP server tools via SSE transport', category: 'integration', route: '/agents/mcp-tool' },
  { id: 'gemini-vectorize', name: 'Gemini Vectorize Agent', description: "Generates text embeddings using Google's Gemini text-embedding-004 model", category: 'ai-service', route: '/agents/gemini-vectorize' },
  { id: 'chromadb', name: 'ChromaDB Agent', description: 'Vector storage and retrieval using ChromaDB. Supports local and cloud deployments.', category: 'database', route: '/agents/chromadb' },
  { id: 'gitmcp', name: 'GitMCP Documentation Agent', description: 'Fetches and chunks GitHub repository documentation via gitmcp.io MCP servers', category: 'integration', route: '/agents/gitmcp' },
  { id: 'rag', name: 'RAG Intelligence Agent', description: 'Generates natural language answers based on provided context using Gemini', category: 'intelligence', route: '/agents/rag' },
  { id: 'chat', name: 'Q&A Context Chat Agent', description: 'Orchestrates RAG pipeline: vectorization, storage, retrieval and answer generation', category: 'chat', route: '/agents/chat' },
] as const;
