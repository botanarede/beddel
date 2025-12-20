/**
 * Gemini Vectorize Agent Schema - Zod validation schemas
 * Safe for both client and server
 */

import { z } from 'zod';

export const GeminiVectorizeInputSchema = z.object({
  action: z.enum(['embedSingle', 'embedBatch']),
  text: z.string().optional(),
  texts: z.array(z.string()).optional(),
});

export const GeminiVectorizeOutputSchema = z.object({
  success: z.boolean(),
  vector: z.array(z.number()).optional(),
  vectors: z.array(z.array(z.number())).optional(),
  error: z.string().optional(),
});

export type GeminiVectorizeInput = z.infer<typeof GeminiVectorizeInputSchema>;
export type GeminiVectorizeOutput = z.infer<typeof GeminiVectorizeOutputSchema>;
