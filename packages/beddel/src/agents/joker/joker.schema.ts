/**
 * Joker Agent Schema - Zod validation schemas
 * Safe for both client and server
 */

import { z } from 'zod';

export const JokerInputSchema = z.object({}).optional();

export const JokerOutputSchema = z.object({
  response: z.string(),
});

export type JokerInput = z.infer<typeof JokerInputSchema>;
export type JokerOutput = z.infer<typeof JokerOutputSchema>;
