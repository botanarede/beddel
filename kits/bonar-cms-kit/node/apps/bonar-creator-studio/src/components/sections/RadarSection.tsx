/**
 * RadarSection — schema-driven wrapper for the RadarLayout component.
 *
 * Accepts SectionComponentProps and extracts noticias data from the
 * resolved collection binding. Products are loaded from the local cache
 * at build time.
 *
 * Registered in the component registry with key "RadarSection".
 */

import { RadarLayout } from './RadarLayout'
import type { SectionComponentProps } from '@/registry/types'
import type { RadarArticle, RadarProduct } from '@/types/radar'
import { weekDateSlug } from '@/types/radar'
import { loadCachedTable } from '@/lib/load-cache'

export function RadarSection({ data }: SectionComponentProps) {
  // Articles come from the resolved data binding (collection: "noticias")
  const articles = (data ?? []) as RadarArticle[]

  // Products loaded from local cache at build time
  const products = loadCachedTable<RadarProduct>('produtos')

  // Derive edition week from the first article's publishedAt or fallback
  const editionWeek = articles.length > 0
    ? weekDateSlug(articles[0].publishedAt)
    : weekDateSlug(new Date().toISOString().split('T')[0])

  if (articles.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading radar content...</p>
      </div>
    )
  }

  return <RadarLayout articles={articles} products={products} editionWeek={editionWeek} />
}
