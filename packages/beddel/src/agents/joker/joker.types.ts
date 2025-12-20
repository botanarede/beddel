/**
 * Joker Agent Types - Shared between client and server
 */

/**
 * Parameters for joke generation
 */
export interface JokeHandlerParams {
  prompt?: string;
  temperature?: number;
  maxTokens?: number;
}

/**
 * Result from joke generation
 */
export interface JokeHandlerResult {
  text: string;
  metadata: {
    model_used: string;
    processing_time: number;
    temperature: number;
    max_tokens: number | null;
    prompt_used: string;
  };
}

/**
 * Joker agent metadata
 */
export interface JokerMetadata {
  id: 'joker';
  name: string;
  description: string;
  category: 'utility';
  route: '/agents/joker';
}
