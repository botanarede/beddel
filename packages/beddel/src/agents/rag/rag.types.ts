/**
 * RAG Agent Types - Shared between client and server
 */

/**
 * Conversation message
 */
export interface ConversationMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

/**
 * Parameters for RAG answer generation
 */
export interface RagHandlerParams {
  query: string;
  context?: string;
  documents?: string;
  history?: ConversationMessage[];
}

/**
 * Result from RAG answer generation
 */
export interface RagHandlerResult {
  response: string;
  answer: string;
  timestamp: string;
  error?: string;
}

/**
 * RAG agent metadata
 */
export interface RagMetadata {
  id: 'rag';
  name: string;
  description: string;
  category: 'intelligence';
  route: '/agents/rag';
  tags: string[];
}
