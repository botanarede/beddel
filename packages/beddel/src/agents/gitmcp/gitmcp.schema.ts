/**
 * GitMCP Agent Schema - Zod validation schemas
 * Safe for both client and server
 */

import { z } from 'zod';

export const GitMcpInputSchema = z.object({
  gitmcp_url: z.string().url(),
});

export const GitMcpOutputSchema = z.object({
  success: z.boolean(),
  chunks: z.array(z.string()).optional(),
  source: z.string().optional(),
  error: z.string().optional(),
});

export type GitMcpInput = z.infer<typeof GitMcpInputSchema>;
export type GitMcpOutput = z.infer<typeof GitMcpOutputSchema>;
