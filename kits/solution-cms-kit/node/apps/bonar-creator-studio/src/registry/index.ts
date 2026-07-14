/**
 * Component Registry — uses @botanarede/core manifest-gated registry builder.
 */
import { buildRegistry, resolveComponent as coreResolveComponent } from '@botanarede/core'
import type { SectionComponent } from './types'
import { appManifest } from './manifest'

// Component imports from shared UI package
import {
  HeroCarousel,
  EventGrid,
  LunchSection,
  MenuDisplay,
  ContactTabs,
  PhotoGallery,
  StructuredData,
  MarkdownPage,
  MembersGrid,
  MediaGallery,
  SiteFooter,
} from '@botanarede/ui-react'
import { ContactSectionConnected } from '@/components/sections/ContactSectionConnected'
import { ContactTabsAdvanced } from '@/components/sections/ContactTabsAdvanced'

// Legacy components (kept for backward compatibility)
import { HeroSection } from '@/components/sections/HeroSection'
import { AboutSection } from '@/components/sections/AboutSection'
import { ServicesSection } from '@/components/sections/ServicesSection'
import { CTASection } from '@/components/sections/CTASection'
import { FooterSection } from '@/components/sections/FooterSection'
import { RadarSection } from '@/components/sections/RadarSection'

const COMPONENT_MAP: Record<string, SectionComponent> = {
  HeroCarousel,
  EventGrid,
  LunchSection,
  MenuDisplay,
  ContactTabs,
  PhotoGallery,
  StructuredData,
  MarkdownPage,
  MembersGrid,
  MediaGallery,
  ContactSection: ContactSectionConnected,
  ContactTabsAdvanced,
  SiteFooter,
  // Legacy components
  AboutSection,
  ServicesSection,
  CTASection,
  FooterSection,
  RadarSection,
}

// Build the manifest-gated registry (frozen, immutable)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const registry = buildRegistry(appManifest, COMPONENT_MAP as any)

/**
 * Resolves a component type string to a React component.
 * Returns null for unregistered types (does not throw).
 */
export function resolveComponent(type: string): SectionComponent | null {
  return coreResolveComponent(registry, type) as SectionComponent | null
}

/**
 * Registers a component at runtime. Useful for lazy-loaded or
 * tenant-specific components added after initial bundle.
 */
export function registerComponent(type: string, component: SectionComponent): void {
  // Note: runtime registration bypasses the manifest allowlist.
  // This is intentional for dynamic loading scenarios.
  ;(COMPONENT_MAP as Record<string, SectionComponent>)[type] = component
}

export type { SectionComponent, SectionComponentProps } from './types'
