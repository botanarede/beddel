/**
 * RAG Agent Schema - Zod validation schemas
 * Safe for both client and server
 */

import { z } from 'zod';

export const RagInputSchema = z.object({
  query: z.string().min(1),
  context: z.string().optional(),
  documents: z.string().optional(),
  history: z.array(z.object({
    role: z.enum(['user', 'assistant', 'system']),
    content: z.string(),
  })).optional(),
});

export const RagOutputSchema = z.object({
  response: z.string(),
  answer: z.string().optional(),
  timestamp: z.string().optional(),
  error: z.string().optional(),
});

export type RagInput = z.infer<typeof RagInputSchema>;
export type RagOutput = z.infer<typeof RagOutputSchema>;
