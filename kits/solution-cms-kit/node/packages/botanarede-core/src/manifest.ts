import type { ZodType } from 'zod';
import type { TenantConfig } from '@botanarede/schema';

export interface ManifestEntry {
  type: string;
  displayName: string;
  category: string;
  allowedSlots?: string[];
  propsSchema?: ZodType;
}

export type ComponentManifest = Record<string, ManifestEntry>;

export function createManifest(entries: ManifestEntry[]): ComponentManifest {
  const manifest: ComponentManifest = {};
  for (const entry of entries) {
    manifest[entry.type] = entry;
  }
  return manifest;
}

export function isAllowed(manifest: ComponentManifest, type: string): boolean {
  return Object.prototype.hasOwnProperty.call(manifest, type);
}

export function validateManifestCompatibility(
  manifest: ComponentManifest,
  config: TenantConfig,
): Array<{ type: string; message: string }> {
  const unknownTypes = new Set<string>();

  for (const comp of Object.values(config.components)) {
    if (!comp) continue;
    if (!isAllowed(manifest, comp.type)) {
      unknownTypes.add(comp.type);
    }
  }

  for (const page of Object.values(config.pages)) {
    if (!page) continue;
    for (const section of page.sections) {
      if (!isAllowed(manifest, section.type)) {
        unknownTypes.add(section.type);
      }
    }
  }

  return Array.from(unknownTypes).map((type) => ({
    type,
    message: `Component type "${type}" is not in the component manifest allowlist`,
  }));
}
