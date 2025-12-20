/**
 * Chat Agent Schema - Zod validation schemas
 * Safe for both client and server
 */

import { z } from 'zod';

export const ChatInputSchema = z.object({
  messages: z.array(z.object({
    role: z.enum(['user', 'assistant', 'system']),
    content: z.string(),
  })),
  query: z.string().optional(),
  knowledge_sources: z.array(z.string()).optional(),
});

export const ChatOutputSchema = z.object({
  response: z.string(),
  timestamp: z.string(),
  execution_steps: z.array(z.object({
    agent: z.string(),
    action: z.string(),
    status: z.enum(['running', 'success', 'error']),
    startTime: z.number(),
    endTime: z.number().optional(),
    duration: z.number().optional(),
    error: z.string().optional(),
  })).optional(),
  total_duration: z.number().optional(),
});

export type ChatInput = z.infer<typeof ChatInputSchema>;
export type ChatOutput = z.infer<typeof ChatOutputSchema>;
