import { z } from 'zod';

export const ComponentDefinitionSchema: z.ZodType<{
  type: string;
  props: Record<string, unknown>;
  children?: Array<{ type: string; props: Record<string, unknown>; children?: unknown[] }>;
}> = z.object({
  type: z.string(),
  props: z.record(z.string(), z.unknown()),
  children: z.lazy(() => z.array(ComponentDefinitionSchema)).optional(),
});

export type ComponentDefinition = z.infer<typeof ComponentDefinitionSchema>;
