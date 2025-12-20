/**
 * ChromaDB Agent - Public exports (client-safe)
 */

// Schema exports (client-safe)
export { ChromaDBInputSchema, ChromaDBOutputSchema } from './chromadb.schema';
export type { ChromaDBInput, ChromaDBOutput } from './chromadb.schema';

// Type exports (client-safe)
export type { ChromaDBHandlerParams, ChromaDBHandlerResult, ChromaDBSearchResult, ChromaDBMetadata } from './chromadb.types';

// Metadata (client-safe)
export const chromadbMetadata = {
  id: 'chromadb',
  name: 'ChromaDB Agent',
  description: 'Vector storage and retrieval using ChromaDB. Supports local and cloud deployments.',
  category: 'database',
  route: '/agents/chromadb',
  tags: ['chromadb', 'storage', 'vector-db', 'rag'],
} as const;
