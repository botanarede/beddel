/**
 * Gemini Vectorize Agent - Public exports (client-safe)
 */

// Schema exports (client-safe)
export { GeminiVectorizeInputSchema, GeminiVectorizeOutputSchema } from './gemini-vectorize.schema';
export type { GeminiVectorizeInput, GeminiVectorizeOutput } from './gemini-vectorize.schema';

// Type exports (client-safe)
export type { VectorizeHandlerParams, VectorizeHandlerResult, GeminiVectorizeMetadata } from './gemini-vectorize.types';

// Metadata (client-safe)
export const geminiVectorizeMetadata = {
  id: 'gemini-vectorize',
  name: 'Gemini Vectorize Agent',
  description: "Generates text embeddings using Google's Gemini text-embedding-004 model",
  category: 'ai-service',
  route: '/agents/gemini-vectorize',
  tags: ['embeddings', 'gemini', 'ai', 'vectorization'],
} as const;
