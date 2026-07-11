import { z } from 'zod';

import { TenantMetadataSchema } from './metadata';
import { DesignTokensSchema } from './design-tokens';
import { PageDefinitionSchema } from './page';
import { LayoutDefinitionSchema } from './layout';
import { ComponentDefinitionSchema } from './component';
import { NavigationConfigSchema } from './navigation';
import { SiteDefaultsSchema } from './site-defaults';

export const CacheConfigSchema = z.object({
  publicTables: z.array(z.string()),
  contentPaths: z.array(z.string()).optional(),
}).strict();

export type CacheConfig = z.infer<typeof CacheConfigSchema>;

export const TenantConfigSchema = z.object({
  metadata: TenantMetadataSchema,
  designTokens: DesignTokensSchema,
  pages: z.record(z.string(), PageDefinitionSchema),
  layouts: z.record(z.string(), LayoutDefinitionSchema),
  components: z.record(z.string(), ComponentDefinitionSchema),
  navigation: NavigationConfigSchema,
  features: z.record(z.string(), z.boolean()).optional(),
  siteDefaults: SiteDefaultsSchema.optional(),
  cacheConfig: CacheConfigSchema.optional(),
}).strict();

export type TenantConfig = z.infer<typeof TenantConfigSchema>;
