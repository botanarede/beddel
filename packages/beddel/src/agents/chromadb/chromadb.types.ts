/**
 * ChromaDB Agent Types - Shared between client and server
 */

/**
 * Parameters for ChromaDB operations
 */
export interface ChromaDBHandlerParams {
  action: 'hasData' | 'store' | 'search';
  collection_name: string;
  min_count?: number;
  ids?: string[];
  vectors?: number[][];
  documents?: string[];
  metadatas?: Record<string, unknown>[];
  query_vector?: number[];
  limit?: number;
}

/**
 * Search result item
 */
export interface ChromaDBSearchResult {
  text: string | null;
  metadata: Record<string, unknown> | null;
  distance: number | null;
}

/**
 * Result from ChromaDB operations
 */
export interface ChromaDBHandlerResult {
  success: boolean;
  has_data?: boolean;
  count?: number;
  stored_count?: number;
  results?: ChromaDBSearchResult[];
  documents?: string;
  error?: string;
}

/**
 * ChromaDB agent metadata
 */
export interface ChromaDBMetadata {
  id: 'chromadb';
  name: string;
  description: string;
  category: 'database';
  route: '/agents/chromadb';
  tags: string[];
}
