import { createManifest } from '@botanarede/core'

/**
 * Component manifest for creator-studio.
 * Defines the allowlist of components that can be rendered from tenant JSON.
 */
export const appManifest = createManifest([
  { type: 'HeroCarousel', displayName: 'Hero Carousel', category: 'section' },
  { type: 'EventGrid', displayName: 'Event Grid', category: 'section' },
  { type: 'LunchSection', displayName: 'Lunch Section', category: 'section' },
  { type: 'MenuDisplay', displayName: 'Menu Display', category: 'section' },
  { type: 'ContactTabs', displayName: 'Contact Tabs', category: 'section' },
  { type: 'ContactTabsAdvanced', displayName: 'Contact Tabs (Advanced)', category: 'section' },
  { type: 'PhotoGallery', displayName: 'Photo Gallery', category: 'section' },
  { type: 'StructuredData', displayName: 'Structured Data', category: 'meta' },
  { type: 'MarkdownPage', displayName: 'Markdown Page', category: 'content' },
  { type: 'HeroSection', displayName: 'Hero Section', category: 'section' },
  { type: 'AboutSection', displayName: 'About Section', category: 'section' },
  { type: 'ServicesSection', displayName: 'Services Section', category: 'section' },
  { type: 'CTASection', displayName: 'CTA Section', category: 'section' },
  { type: 'FooterSection', displayName: 'Footer Section', category: 'section' },
  { type: 'RadarSection', displayName: 'Radar Section', category: 'content' },
  { type: 'MembersGrid', displayName: 'Members Grid', category: 'section' },
  { type: 'MediaGallery', displayName: 'Media Gallery', category: 'section' },
  { type: 'ContactSection', displayName: 'Contact Section', category: 'section' },
  { type: 'SiteFooter', displayName: 'Site Footer', category: 'section' },
])
