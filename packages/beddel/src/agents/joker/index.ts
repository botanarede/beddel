/**
 * Joker Agent - Public exports (client-safe)
 */

// Schema exports (client-safe)
export { JokerInputSchema, JokerOutputSchema } from './joker.schema';
export type { JokerInput, JokerOutput } from './joker.schema';

// Type exports (client-safe)
export type { JokeHandlerParams, JokeHandlerResult, JokerMetadata } from './joker.types';

// Metadata (client-safe)
export const jokerMetadata = {
  id: 'joker',
  name: 'Joker Agent',
  description: 'Tells jokes using Gemini Flash',
  category: 'utility',
  route: '/agents/joker',
} as const;
