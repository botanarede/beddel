/** Types for the Radar Prana editorial hub */

export interface RadarArticle {
  id: string
  title: string
  summary: string
  pillar: string
  tags: string[]
  source: string
  sourceUrl: string
  image: string
  publishedAt: string
  featured: boolean
  layout: 'wide' | 'standard' | 'compact'
  relatedProductIds: string[]
  body: string
}

export interface ProductCreator {
  name: string
  credential: string
}

export interface ProductPricing {
  currency: string
  price: number
  originalPrice: number
  installments: string
}

export interface ProductImage {
  url: string
  alt: string
}

export interface ProductLinks {
  salesPage: string
  checkout: string
}

export interface RadarProduct {
  id: string
  title: string
  shortDescription: string
  category: string
  vertical: string
  creator: ProductCreator
  pricing: ProductPricing
  image: ProductImage
  links: ProductLinks
  platform: string
  guarantee: string
  relatedArticleIds: string[]
  badge: string
}

export interface RadarArticlesData {
  version: string
  updatedAt: string
  articles: RadarArticle[]
}

export interface RadarProductsData {
  version: string
  updatedAt: string
  products: RadarProduct[]
}

/**
 * Derives the week-date slug from the edition's updatedAt field.
 * Format: "2026-04-30" → "2026-w18" (ISO week number).
 */
export function weekDateSlug(updatedAt: string): string {
  const d = new Date(updatedAt + 'T12:00:00Z')
  const year = d.getUTCFullYear()
  // ISO week calculation
  const dayOfYear = Math.floor((d.getTime() - new Date(Date.UTC(year, 0, 1)).getTime()) / 86400000) + 1
  const weekDay = (d.getUTCDay() + 6) % 7 // Mon=0
  const weekNum = Math.floor((dayOfYear - weekDay + 10) / 7)
  return `${year}-w${String(weekNum).padStart(2, '0')}`
}

/** Build the canonical URL path for an article */
export function articlePath(weekSlug: string, slug: string): string {
  return `/radar/${weekSlug}/${slug}/`
}

/** Pillar display configuration */
export const PILLAR_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  'saude-mental': { label: 'Saúde Mental', color: '#2d6a4f', bg: '#95d5b2' },
  'educacao-integrativa': { label: 'Educação Integrativa', color: '#7c3aed', bg: '#ddd6fe' },
  mercado: { label: 'Mercado', color: '#b45309', bg: '#fde68a' },
  alimentacao: { label: 'Alimentação', color: '#dc2626', bg: '#fecaca' },
  ciencia: { label: 'Ciência', color: '#0369a1', bg: '#bae6fd' },
}
