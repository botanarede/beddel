import type { ComponentType } from 'react';

/**
 * Props contract for all registry-managed section components.
 *
 * Static props come from `section.props` in tenant JSON.
 * `data` is populated by the data binding resolver (if the section
 * declares a `dataBinding`).
 * `tenantId` is injected by the page renderer for asset resolution.
 */
export interface SectionComponentProps {
  [key: string]: unknown;
  data?: unknown[];
  tenantId?: string;
}

export type SectionComponent = ComponentType<SectionComponentProps>;
