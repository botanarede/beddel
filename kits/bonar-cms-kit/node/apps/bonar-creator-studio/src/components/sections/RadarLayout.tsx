'use client'

import { useCallback, useEffect, useState } from 'react'

import { RadarSidebar } from './RadarSidebar'
import { RadarArticleView } from './RadarArticleView'
import type { RadarArticle, RadarProduct } from '@/types/radar'
import { trackListingView } from '@/lib/radar-tracking'

interface RadarLayoutProps {
  articles: RadarArticle[]
  products: RadarProduct[]
  editionWeek: string
}

export function RadarLayout({ articles, products, editionWeek }: RadarLayoutProps) {
  const [activeId, setActiveId] = useState<string>(articles[0]?.id ?? '')

  useEffect(() => {
    trackListingView(editionWeek, articles.length)
  }, [])

  const activeArticle = articles.find((a) => a.id === activeId) ?? articles[0]

  // Resolve the related product for the active article
  const activeProduct = activeArticle?.relatedProductIds[0]
    ? products.find((p) => p.id === activeArticle.relatedProductIds[0])
    : undefined

  const handleSelect = useCallback((id: string) => {
    setActiveId(id)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <div className="min-h-screen bg-white">
      {/* Sidebar — link-based navigation to individual article pages */}
      <RadarSidebar
        articles={articles}
        activeId={activeId}
        editionWeek={editionWeek}
      />

      {/* Main content — offset by sidebar width on desktop */}
      <main className="min-h-screen pt-10 md:ml-[340px] lg:ml-[380px]">
        {activeArticle && (
          <RadarArticleView
            key={activeArticle.id}
            article={activeArticle}
            product={activeProduct}
          />
        )}

        {/* Footer */}
        <footer className="border-t py-6">
          <div className="mx-auto flex max-w-3xl flex-col items-center gap-2 px-6 text-xs text-muted-foreground md:flex-row md:justify-between">
            <span>© {new Date().getFullYear()} Demo Brand</span>
            <div className="flex gap-4">
              <a href="/" className="hover:text-foreground">Home</a>
              <a href="/politica-de-privacidade/" className="hover:text-foreground">
                Política de Privacidade
              </a>
              <a href="mailto:contact@example.com" className="hover:text-foreground">
                contact@example.com
              </a>
            </div>
          </div>
        </footer>
      </main>
    </div>
  )
}
