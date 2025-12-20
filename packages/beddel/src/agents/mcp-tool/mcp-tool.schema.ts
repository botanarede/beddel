/**
 * MCP Tool Agent Schema - Zod validation schemas
 * Safe for both client and server
 */

import { z } from 'zod';

export const McpToolInputSchema = z.object({
  server_url: z.string().url(),
  tool_name: z.string().min(1),
  tool_arguments: z.record(z.string(), z.unknown()).optional(),
});

export const McpToolOutputSchema = z.object({
  success: z.boolean(),
  data: z.string().optional(),
  tool_names: z.array(z.string()).optional(),
  error: z.string().optional(),
});

export type McpToolInput = z.infer<typeof McpToolInputSchema>;
export type McpToolOutput = z.infer<typeof McpToolOutputSchema>;
