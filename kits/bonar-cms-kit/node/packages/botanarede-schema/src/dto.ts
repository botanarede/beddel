import { z } from 'zod';

import { TenantMetadataSchema } from './metadata';
import { DesignTokensSchema } from './design-tokens';
import { PageDefinitionSchema } from './page';
import { LayoutDefinitionSchema } from './layout';
import { ComponentDefinitionSchema } from './component';
import { NavigationConfigSchema } from './navigation';
import type { TenantConfig } from './tenant-config';

// --- Public Metadata Schema ---
// Pick only public-safe fields from TenantMetadataSchema
export const PublicMetadataSchema = TenantMetadataSchema.pick({
  id: true,
  name: true,
  status: true,
  domains: true,
  publishedVersionId: true,
}).strict();

export type PublicMetadata = z.infer<typeof PublicMetadataSchema>;

// --- Public Tenant Config Schema ---
export const PublicTenantConfigSchema = z
  .object({
    metadata: PublicMetadataSchema,
    designTokens: DesignTokensSchema,
    pages: z.record(z.string(), PageDefinitionSchema),
    layouts: z.record(z.string(), LayoutDefinitionSchema),
    components: z.record(z.string(), ComponentDefinitionSchema),
    navigation: NavigationConfigSchema,
  })
  .strict();

export type PublicTenantConfig = z.infer<typeof PublicTenantConfigSchema>;

// --- Admin Metadata Schema ---
export const AdminMetadataSchema = TenantMetadataSchema.extend({
  draftStatus: z.enum(['clean', 'dirty', 'pending-review']).optional(),
  lastEditor: z.string().optional(),
  lastEditedAt: z.string().optional(),
}).strict();

export type AdminMetadata = z.infer<typeof AdminMetadataSchema>;

// --- Admin Tenant Config Schema ---
export const AdminTenantConfigSchema = z
  .object({
    metadata: AdminMetadataSchema,
    designTokens: DesignTokensSchema,
    pages: z.record(z.string(), PageDefinitionSchema),
    layouts: z.record(z.string(), LayoutDefinitionSchema),
    components: z.record(z.string(), ComponentDefinitionSchema),
    navigation: NavigationConfigSchema,
    features: z.record(z.string(), z.boolean()).optional(),
  })
  .strict();

export type AdminTenantConfig = z.infer<typeof AdminTenantConfigSchema>;


// --- Projection Functions ---

/**
 * Immutable projection: strips features, admin metadata fields,
 * and filters out pages with visibility: "admin".
 */
export function toPublicDTO(config: TenantConfig): PublicTenantConfig {
  const { id, name, status, domains, publishedVersionId } = config.metadata;
  const metadata: PublicMetadata = {
    id,
    name,
    status,
    domains: [...domains],
    ...(publishedVersionId !== undefined ? { publishedVersionId } : {}),
  };

  // Filter out admin-visibility pages (default is "public" when absent)
  const pages = Object.fromEntries(
    Object.entries(config.pages).filter(([, page]) => {
      if (!page) return false;
      return page.visibility !== 'admin';
    }),
  );

  return {
    metadata,
    designTokens: { ...config.designTokens },
    pages,
    layouts: { ...config.layouts },
    components: { ...config.components },
    navigation: { ...config.navigation },
  };
}

/**
 * Returns full config with admin metadata merged.
 */
export function toAdminDTO(
  config: TenantConfig,
  adminMeta?: { draftStatus?: 'clean' | 'dirty' | 'pending-review'; lastEditor?: string; lastEditedAt?: string },
): AdminTenantConfig {
  const metadata: AdminMetadata = {
    ...config.metadata,
    ...(adminMeta?.draftStatus !== undefined
      ? { draftStatus: adminMeta.draftStatus }
      : {}),
    ...(adminMeta?.lastEditor !== undefined ? { lastEditor: adminMeta.lastEditor } : {}),
    ...(adminMeta?.lastEditedAt !== undefined ? { lastEditedAt: adminMeta.lastEditedAt } : {}),
  };

  return {
    metadata,
    designTokens: { ...config.designTokens },
    pages: { ...config.pages },
    layouts: { ...config.layouts },
    components: { ...config.components },
    navigation: { ...config.navigation },
    ...(config.features !== undefined ? { features: { ...config.features } } : {}),
  };
}
