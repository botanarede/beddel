'use client'

import { useEffect } from 'react'
import { RadarSidebar } from './RadarSidebar'
import { RadarArticleView } from './RadarArticleView'
import { RadarDisclaimer } from './RadarDisclaimer'
import type { RadarArticle, RadarProduct } from '@/types/radar'
import { trackArticleView } from '@/lib/radar-tracking'

interface RadarArticlePageProps {
  article: RadarArticle
  product?: RadarProduct
  allArticles: RadarArticle[]
  editionWeek: string
}

export function RadarArticlePage({ article, product, allArticles, editionWeek }: RadarArticlePageProps) {
  useEffect(() => {
    trackArticleView(article, editionWeek)
  }, [article.id])

  return (
    <div className="min-h-screen bg-white">
      {/* Sidebar — link-based navigation */}
      <RadarSidebar
        articles={allArticles}
        activeId={article.id}
        editionWeek={editionWeek}
        sourcePage="article"
      />

      {/* Main content — offset by sidebar width on desktop */}
      <main className="min-h-screen pt-10 md:ml-[340px] lg:ml-[380px]">
        {/* Full article with product embed */}
        <RadarArticleView article={article} product={product} />

        {/* Disclaimer — only shown on individual pages that have a product */}
        {product && <RadarDisclaimer />}

        {/* Footer */}
        <footer className="border-t py-6">
          <div className="mx-auto flex max-w-3xl flex-col items-center gap-2 px-6 text-xs text-muted-foreground md:flex-row md:justify-between">
            <span>© {new Date().getFullYear()} Your Brand</span>
            <div className="flex gap-4">
              <a href="/" className="hover:text-foreground">Home</a>
              <a href="/radar/" className="hover:text-foreground">Radar</a>
              <a href="/politica-de-privacidade/" className="hover:text-foreground">
                Privacidade
              </a>
            </div>
          </div>
        </footer>
      </main>
    </div>
  )
}
