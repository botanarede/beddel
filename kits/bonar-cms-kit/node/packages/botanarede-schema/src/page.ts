import { z } from 'zod';
import { DataBindingSchema } from './query';

export const SectionSchema = z.object({
  type: z.string(),
  id: z.string().optional(),
  slot: z.string().optional(),
  props: z.record(z.string(), z.unknown()),
  dataBinding: DataBindingSchema.optional(),
  featureGate: z.string().optional(),
}).strict();

export type Section = z.infer<typeof SectionSchema>;

export const PageDefinitionSchema = z.object({
  route: z.string(),
  title: z.string(),
  description: z.string().optional(),
  ogImage: z.string().optional(),
  layoutRef: z.string(),
  sections: z.array(SectionSchema),
  visibility: z.enum(['public', 'admin']).optional(),
}).strict();

export type PageDefinition = z.infer<typeof PageDefinitionSchema>;
