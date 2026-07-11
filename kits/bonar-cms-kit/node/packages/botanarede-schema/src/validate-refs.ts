import type { TenantConfig } from './tenant-config';

export interface LayoutRefError {
  page: string;
  layoutRef: string;
  message: string;
}

export interface LayoutRefValidationResult {
  valid: boolean;
  errors: LayoutRefError[];
}

export function validateLayoutRefs(config: TenantConfig): LayoutRefValidationResult {
  const errors: LayoutRefError[] = [];

  for (const [pageKey, page] of Object.entries(config.pages)) {
    const layout = config.layouts[page.layoutRef];
    if (layout === undefined) {
      errors.push({
        page: pageKey,
        layoutRef: page.layoutRef,
        message: `Page "${pageKey}" references layout "${page.layoutRef}" which does not exist in config.layouts`,
      });
    }
  }

  return { valid: errors.length === 0, errors };
}
