/**
 * Chat Agent - Public exports (client-safe)
 */

// Schema exports (client-safe)
export { ChatInputSchema, ChatOutputSchema } from './chat.schema';
export type { ChatInput, ChatOutput } from './chat.schema';

// Type exports (client-safe)
export type { ChatHandlerParams, ChatHandlerResult, ChatMetadata } from './chat.types';

// Metadata (client-safe)
export const chatMetadata = {
  id: 'chat',
  name: 'Q&A Context Chat Agent',
  description: 'Orchestrates RAG pipeline: vectorization, storage, retrieval and answer generation',
  category: 'chat',
  route: '/agents/chat',
  knowledge_sources: ['gitmcp-agent'],
  tags: ['chat', 'orchestrator', 'rag', 'qa'],
} as const;
