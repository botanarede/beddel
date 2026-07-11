import { z } from 'zod';

export const TenantMetadataSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.enum(['active', 'inactive', 'suspended']),
  domains: z.array(z.string()),
  publishedVersionId: z.string().optional(),
  features: z.record(z.string(), z.boolean()).optional(),
  /** Overrides the output folder name used by next.config.mjs. Default behavior (no exportDomain) uses metadata.id. */
  exportDomain: z.string().optional(),
}).strict();

export type TenantMetadata = z.infer<typeof TenantMetadataSchema>;
