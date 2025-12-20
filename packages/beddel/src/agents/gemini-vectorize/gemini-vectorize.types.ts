/**
 * Gemini Vectorize Agent Types - Shared between client and server
 */

/**
 * Parameters for vectorization
 */
export interface VectorizeHandlerParams {
  action: 'embedSingle' | 'embedBatch';
  text?: string;
  texts?: string[];
}

/**
 * Result from vectorization
 */
export interface VectorizeHandlerResult {
  success: boolean;
  vector?: number[];
  vectors?: number[][];
  error?: string;
}

/**
 * Gemini Vectorize agent metadata
 */
export interface GeminiVectorizeMetadata {
  id: 'gemini-vectorize';
  name: string;
  description: string;
  category: 'ai-service';
  route: '/agents/gemini-vectorize';
  tags: string[];
}
