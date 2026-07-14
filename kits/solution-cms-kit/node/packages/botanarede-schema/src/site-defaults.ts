import { z } from 'zod';

export const GeoSchema = z.object({
  lat: z.number(),
  lng: z.number(),
}).strict();

export const AddressSchema = z.object({
  street: z.string(),
  city: z.string(),
  state: z.string(),
  zip: z.string(),
  country: z.string(),
  geo: GeoSchema.optional(),
  googleMapsQuery: z.string().optional(),
}).strict();

export const BrandingSchema = z.object({
  logo: z.string(),
  logoWhite: z.string().optional(),
  favicon: z.string().optional(),
  ogImage: z.string().optional(),
  primaryColor: z.string(),
  accentColor: z.string(),
  fontHeading: z.string().optional(),
  fontBody: z.string().optional(),
}).strict();

export const OpeningHoursSchema = z.object({
  dayOfWeek: z.array(z.string()),
  opens: z.string(),
  closes: z.string(),
  description: z.string().optional(),
}).strict();

export const ReservationConfigSchema = z.object({
  timeSlots: z.array(z.string()),
  defaultCapacityPerSlot: z.number(),
  blockedDates: z.array(z.string()),
  minGuests: z.number(),
  maxGuests: z.number(),
}).strict();

export const FAQItemSchema = z.object({
  question: z.string(),
  answer: z.string(),
}).strict();

export const SiteDefaultsSchema = z.object({
  name: z.string(),
  tagline: z.string().optional(),
  description: z.string().optional(),
  url: z.string().optional(),
  locale: z.string().optional(),
  email: z.string().optional(),
  phone: z.string().optional(),
  whatsapp: z.string().optional(),
  address: AddressSchema.optional(),
  social: z.record(z.string(), z.string().optional()).optional(),
  branding: BrandingSchema,
  theme: z.record(z.string(), z.unknown()).optional(),
  analytics: z.object({
    gtmId: z.string().optional(),
  }).optional(),
  firebase: z.object({
    projectId: z.string().optional(),
    storageBucket: z.string().optional(),
  }).optional(),
  businessTypes: z.array(z.string()).optional(),
  openingHours: z.array(OpeningHoursSchema).optional(),
  cuisineTypes: z.array(z.string()).optional(),
  maxCapacity: z.number().optional(),
  reservations: ReservationConfigSchema.optional(),
  faq: z.array(FAQItemSchema).optional(),
}).strict();

export type SiteDefaults = z.infer<typeof SiteDefaultsSchema>;
export type Address = z.infer<typeof AddressSchema>;
export type Branding = z.infer<typeof BrandingSchema>;
export type OpeningHours = z.infer<typeof OpeningHoursSchema>;
export type FAQItem = z.infer<typeof FAQItemSchema>;
