import type { LayoutProps } from './types'

/**
 * Minimal layout — content only, no header or footer.
 * Used for standalone pages like privacy policy, landing pages, etc.
 */
export function MinimalLayout({ children }: LayoutProps) {
  return <main>{children}</main>
}
