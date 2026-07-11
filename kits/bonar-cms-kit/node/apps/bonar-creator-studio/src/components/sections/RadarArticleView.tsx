'use client'

import Image from 'next/image'
import { PillarPill } from '@/components/ui/PillarPill'
import { ProductEmbed } from '@/components/ui/ProductEmbed'
import type { RadarArticle, RadarProduct } from '@/types/radar'

interface RadarArticleViewProps {
  article: RadarArticle
  product?: RadarProduct
  /** When false, hides the product embed (used on listing page). Default: true */
  showProduct?: boolean
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + 'T12:00:00').toLocaleDateString('pt-BR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export function RadarArticleView({ article, product, showProduct = true }: RadarArticleViewProps) {
  const paragraphs = article.body.split('\n\n').filter(Boolean)

  return (
    <article className="mx-auto max-w-3xl px-5 py-10 md:px-8 md:py-16">
      {/* Header */}
      <header>
        <div className="flex items-center gap-3">
          <PillarPill pillar={article.pillar} size="md" />
          {article.featured && (
            <span className="rounded-full bg-[#2d6a4f]/10 px-2.5 py-0.5 text-[10px] font-semibold text-[#2d6a4f]">
              ★ Destaque
            </span>
          )}
        </div>

        <h1 className="mt-4 font-heading text-3xl font-bold leading-[1.15] text-foreground md:text-4xl lg:text-5xl">
          {article.title}
        </h1>

        <p className="mt-4 text-lg leading-relaxed text-muted-foreground md:text-xl">
          {article.summary}
        </p>

        {/* Meta */}
        <div className="mt-6 flex flex-wrap items-center gap-4 border-b border-border/50 pb-6 text-xs text-muted-foreground/60">
          <span>{formatDate(article.publishedAt)}</span>
          <span className="h-1 w-1 rounded-full bg-muted-foreground/30" />
          <span>Fonte: {article.source}</span>
          {article.tags.length > 0 && (
            <>
              <span className="h-1 w-1 rounded-full bg-muted-foreground/30" />
              <span>{article.tags.join(', ')}</span>
            </>
          )}
        </div>
      </header>

      {/* Hero image */}
      <div className="relative mt-8 aspect-[16/9] overflow-hidden rounded-2xl bg-muted">
        <Image
          src={article.image}
          alt={article.title}
          fill
          className="object-cover"
          sizes="(max-width: 768px) 100vw, 720px"
          priority
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/10 to-transparent" />
      </div>

      {/* Body */}
      <div className="mt-10 space-y-5">
        {paragraphs.map((paragraph, i) => (
          <p
            key={i}
            className="text-base leading-[1.8] text-foreground/80 md:text-[17px]"
          >
            {paragraph}
          </p>
        ))}
      </div>

      {/* Product recommendation — only on individual article pages */}
      {showProduct && product && (
        <div className="mt-10 border-t border-border/50 pt-8">
          <p className="mb-1 text-[11px] font-medium uppercase tracking-[0.15em] text-muted-foreground/50">
            Recomendação da redação
          </p>
          <ProductEmbed product={product} article={article} />
        </div>
      )}

      {/* Source link */}
      <div className="mt-10 border-t border-border/50 pt-6">
        <p className="text-xs text-muted-foreground/50">
          Fonte original:{' '}
          <a
            href={article.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#2d6a4f] underline decoration-[#2d6a4f]/30 underline-offset-2 transition-colors hover:text-[#1b4332]"
          >
            {article.source}
          </a>
        </p>
      </div>
    </article>
  )
}
