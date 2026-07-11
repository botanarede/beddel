/**
 * Layout Registry — maps layout reference strings from tenant JSON
 * to layout components.
 *
 * Default layout is "public" when not specified in the page definition.
 */

import type { LayoutComponent } from './types'
import { PublicLayout } from './PublicLayout'
import { MinimalLayout } from './MinimalLayout'

const LAYOUT_REGISTRY: Record<string, LayoutComponent> = {
  public: PublicLayout,
  minimal: MinimalLayout,
}

/**
 * Resolves a layout reference to a layout component.
 * Falls back to PublicLayout when the ref is not found.
 */
export function resolveLayout(ref: string): LayoutComponent {
  return LAYOUT_REGISTRY[ref] ?? LAYOUT_REGISTRY['public']
}

export type { LayoutProps, LayoutComponent } from './types'
