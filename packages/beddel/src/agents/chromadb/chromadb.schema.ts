/**
 * ChromaDB Agent Schema - Zod validation schemas
 * Safe for both client and server
 */

import { z } from 'zod';

export const ChromaDBInputSchema = z.object({
  action: z.enum(['hasData', 'store', 'search']),
  collection_name: z.string().min(1),
  min_count: z.number().optional(),
  ids: z.array(z.string()).optional(),
  vectors: z.array(z.array(z.number())).optional(),
  documents: z.array(z.string()).optional(),
  metadatas: z.array(z.record(z.string(), z.unknown())).optional(),
  query_vector: z.array(z.number()).optional(),
  limit: z.number().optional(),
});

export const ChromaDBOutputSchema = z.object({
  success: z.boolean(),
  has_data: z.boolean().optional(),
  count: z.number().optional(),
  stored_count: z.number().optional(),
  results: z.array(z.object({
    text: z.string().nullable(),
    metadata: z.record(z.string(), z.unknown()).nullable(),
    distance: z.number().nullable(),
  })).optional(),
  documents: z.string().optional(),
  error: z.string().optional(),
});

export type ChromaDBInput = z.infer<typeof ChromaDBInputSchema>;
export type ChromaDBOutput = z.infer<typeof ChromaDBOutputSchema>;
