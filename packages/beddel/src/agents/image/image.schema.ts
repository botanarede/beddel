/**
 * Image Agent Schema - Zod validation schemas
 * Safe for both client and server
 */

import { z } from 'zod';

export const ImageInputSchema = z.object({
  description: z.string().min(5).max(500),
  style: z.enum(['watercolor', 'neon', 'sketch']),
  resolution: z.string().regex(/^[0-9]{3,4}x[0-9]{3,4}$/),
});

export const ImageOutputSchema = z.object({
  image_url: z.string(),
  image_base64: z.string().optional(),
  media_type: z.string().optional(),
  prompt_used: z.string(),
  metadata: z.object({
    model_used: z.string(),
    processing_time: z.number(),
    style: z.string(),
    resolution: z.string(),
  }),
});

export type ImageInput = z.infer<typeof ImageInputSchema>;
export type ImageOutput = z.infer<typeof ImageOutputSchema>;
