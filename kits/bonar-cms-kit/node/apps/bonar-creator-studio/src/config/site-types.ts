/**
 * SiteConfig types — copied from bonar-tickets for self-contained build.
 */

export interface OpeningHoursEntry {
  days: Array<'Monday' | 'Tuesday' | 'Wednesday' | 'Thursday' | 'Friday' | 'Saturday' | 'Sunday'>
  opens: string
  closes: string
  description?: string
}

export interface FaqEntry {
  question: string
  answer: string
}

export interface SiteConfig {
  name: string
  tagline: string
  description: string
  url: string
  locale: string
  email: string
  phone: string
  whatsapp: string
  address: {
    street: string
    city: string
    state: string
    zip: string
    country: string
    geo: { lat: number; lng: number }
    googleMapsQuery: string
  }
  social: {
    instagram?: string
    facebook?: string
    tiktok?: string
    youtube?: string
    twitter?: string
  }
  branding: {
    logo: string
    logoWhite: string
    favicon: string
    ogImage: string
    primaryColor: string
    accentColor: string
    fontHeading?: string
    fontBody?: string
  }
  theme?: { heroStyle?: 'carousel' | 'static' }
  features: {
    events: boolean
    menu: boolean
    photos: boolean
    contact: boolean
    reservations: boolean
    birthdayList: boolean
    corporateEvents: boolean
    faq: boolean
    vip: boolean
    reports: boolean
    symplaImport: boolean
  }
  analytics: { gtmId?: string; googleAnalyticsId?: string }
  firebase: Record<string, unknown>
  businessTypes: string[]
  openingHours: OpeningHoursEntry[]
  cuisineTypes: string[]
  maxCapacity: number
  reservations: {
    timeSlots: string[]
    defaultCapacityPerSlot: number
    blockedDates: string[]
    minGuests: number
    maxGuests: number
  }
  faq: FaqEntry[]
}
