import type { TenantConfig, SiteDefaults } from '@botanarede/schema'
import type { SiteConfig, OpeningHoursEntry, FaqEntry } from './site-types'

export type { SiteConfig }
export type RuntimeSiteConfig = SiteConfig

/**
 * TenantConfig from schema already includes siteDefaults as optional.
 * This alias provides backward compatibility for existing code.
 */
export type TenantJsonExtended = TenantConfig

/**
 * Maps a tenant JSON config to the runtime SiteConfig used by layouts and components.
 * Merges designTokens + siteDefaults + metadata into a flat, fully-resolved object.
 */
export function mapTenantToSiteConfig(tenant: TenantJsonExtended): RuntimeSiteConfig {
  const colors = tenant.designTokens.colors ?? {}
  const typo = tenant.designTokens.typography ?? {}
  const fonts = typo.fontFamilies ?? {}
  const sd: Partial<SiteDefaults> = tenant.siteDefaults ?? {}

  const rawFeatures: Record<string, boolean> = {
    ...(tenant.metadata.features ?? {}),
    ...(tenant.features ?? {}),
  }

  const features: SiteConfig['features'] = {
    events: rawFeatures['events'] ?? false,
    menu: rawFeatures['menu'] ?? false,
    photos: rawFeatures['photos'] ?? false,
    contact: rawFeatures['contact'] ?? false,
    reservations: rawFeatures['reservations'] ?? false,
    birthdayList: rawFeatures['birthdayList'] ?? false,
    corporateEvents: rawFeatures['corporateEvents'] ?? false,
    faq: rawFeatures['faq'] ?? false,
    vip: rawFeatures['vip'] ?? false,
    reports: rawFeatures['reports'] ?? false,
    symplaImport: rawFeatures['symplaImport'] ?? false,
  }

  const primaryRaw = colors['primary']
  const primaryColor = typeof primaryRaw === 'string' ? primaryRaw : (sd.branding?.primaryColor ?? '#3b82f6')
  const accentRaw = colors['accent']
  const accentColor = typeof accentRaw === 'string' ? accentRaw : (sd.branding?.accentColor ?? '#f59e0b')

  return {
    name: sd.name ?? tenant.metadata.name,
    tagline: sd.tagline ?? '',
    description: sd.description ?? '',
    url: sd.url ?? (tenant.metadata.domains[0] ? `https://${tenant.metadata.domains[0]}` : 'https://example.com'),
    locale: sd.locale ?? 'pt-BR',
    email: sd.email ?? '',
    phone: sd.phone ?? '',
    whatsapp: sd.whatsapp ?? '',
    address: {
      street: sd.address?.street ?? '',
      city: sd.address?.city ?? '',
      state: sd.address?.state ?? '',
      zip: sd.address?.zip ?? '',
      country: sd.address?.country ?? 'BR',
      geo: sd.address?.geo ?? { lat: 0, lng: 0 },
      googleMapsQuery: sd.address?.googleMapsQuery ?? '',
    },
    social: (sd.social ?? {}) as SiteConfig['social'],
    branding: {
      logo: sd.branding?.logo ?? '/images/logo.webp',
      logoWhite: sd.branding?.logoWhite ?? '/images/logo-white.webp',
      favicon: sd.branding?.favicon ?? '/favicon.ico',
      ogImage: sd.branding?.ogImage ?? '/images/og/default.jpg',
      primaryColor,
      accentColor,
      fontHeading: fonts['heading'] ?? sd.branding?.fontHeading ?? 'Inter',
      fontBody: fonts['body'] ?? sd.branding?.fontBody ?? 'Inter',
    },
    theme: (sd.theme ?? { heroStyle: 'carousel' }) as SiteConfig['theme'],
    features,
    analytics: sd.analytics ?? {},
    firebase: sd.firebase ?? {},
    businessTypes: sd.businessTypes ?? ['EventVenue'],
    openingHours: (sd.openingHours ?? []).map((h) => ({
      days: h.dayOfWeek as OpeningHoursEntry['days'],
      opens: h.opens,
      closes: h.closes,
      description: h.description,
    })),
    cuisineTypes: sd.cuisineTypes ?? [],
    maxCapacity: sd.maxCapacity ?? 500,
    reservations: sd.reservations ?? { timeSlots: [], defaultCapacityPerSlot: 40, blockedDates: [], minGuests: 1, maxGuests: 10 },
    faq: (sd.faq ?? []) as FaqEntry[],
  }
}
