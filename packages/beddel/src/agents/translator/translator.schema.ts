/**
 * Translator Agent Schema - Zod validation schemas
 * Safe for both client and server
 */

import { z } from 'zod';

export const TranslatorInputSchema = z.object({
  text: z.string().min(1).max(10000),
  source_language: z.string().regex(/^[a-z]{2}$/),
  target_language: z.string().regex(/^[a-z]{2}$/),
});

export const TranslatorOutputSchema = z.object({
  translated_text: z.string(),
  metadata: z.object({
    model_used: z.string(),
    processing_time: z.number(),
    confidence: z.number(),
    supported_languages: z.array(z.string()),
    requested_languages: z.object({
      source: z.string(),
      target: z.string(),
    }),
    prompt_used: z.string(),
  }),
});

export type TranslatorInput = z.infer<typeof TranslatorInputSchema>;
export type TranslatorOutput = z.infer<typeof TranslatorOutputSchema>;
