import { z } from 'zod';

export const SlotDefinitionSchema = z.object({
  name: z.string(),
  description: z.string().optional(),
}).strict();

export type SlotDefinition = z.infer<typeof SlotDefinitionSchema>;

export const LayoutDefinitionSchema = z.object({
  id: z.string(),
  slots: z.array(SlotDefinitionSchema),
  defaultProps: z.record(z.string(), z.unknown()).optional(),
}).strict();

export type LayoutDefinition = z.infer<typeof LayoutDefinitionSchema>;
