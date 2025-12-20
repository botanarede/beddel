/**
 * Client Module - Safe exports for client-side usage
 *
 * This module exports only types and metadata that are safe for client-side usage.
 * It does NOT export any handlers, runtime logic, or server-only code.
 *
 * IMPORTANT: Never import from '../agents' index as it includes server-only registry!
 * Import directly from individual agent folders instead.
 */

// Re-export all shared types and utilities
export * from '../shared';

// Re-export client-specific types
export * from './types';

// Agent metadata exports (client-safe) - import directly from agent folders
export { jokerMetadata } from '../agents/joker';
export { translatorMetadata } from '../agents/translator';
export { imageMetadata } from '../agents/image';
export { mcpToolMetadata } from '../agents/mcp-tool';
export { geminiVectorizeMetadata } from '../agents/gemini-vectorize';
export { chromadbMetadata } from '../agents/chromadb';
export { gitmcpMetadata } from '../agents/gitmcp';
export { ragMetadata } from '../agents/rag';
export { chatMetadata } from '../agents/chat';

// Schema exports (client-safe - for validation)
export { JokerInputSchema, JokerOutputSchema } from '../agents/joker';
export { TranslatorInputSchema, TranslatorOutputSchema } from '../agents/translator';
export { ImageInputSchema, ImageOutputSchema } from '../agents/image';
export { McpToolInputSchema, McpToolOutputSchema } from '../agents/mcp-tool';
export { GeminiVectorizeInputSchema, GeminiVectorizeOutputSchema } from '../agents/gemini-vectorize';
export { ChromaDBInputSchema, ChromaDBOutputSchema } from '../agents/chromadb';
export { GitMcpInputSchema, GitMcpOutputSchema } from '../agents/gitmcp';
export { RagInputSchema, RagOutputSchema } from '../agents/rag';
export { ChatInputSchema, ChatOutputSchema } from '../agents/chat';

/**
 * All agent metadata for UI display
 * Defined here to avoid importing from agents/index.ts which includes server-only registry
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
