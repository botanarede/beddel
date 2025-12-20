/**
 * RAG Agent - Public exports (client-safe)
 */

// Schema exports (client-safe)
export { RagInputSchema, RagOutputSchema } from './rag.schema';
export type { RagInput, RagOutput } from './rag.schema';

// Type exports (client-safe)
export type { RagHandlerParams, RagHandlerResult, ConversationMessage, RagMetadata } from './rag.types';

// Metadata (client-safe)
export const ragMetadata = {
  id: 'rag',
  name: 'RAG Intelligence Agent',
  description: 'Generates natural language answers based on provided context using Gemini',
  category: 'intelligence',
  route: '/agents/rag',
  tags: ['rag', 'gemini', 'qa', 'generation'],
} as const;
