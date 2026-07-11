'use client'

import Image from 'next/image'
import { PillarPill } from './PillarPill'
import { ProductEmbed } from './ProductEmbed'
import type { RadarArticle, RadarProduct } from '@/types/radar'

interface ArticleCardProps {
  article: RadarArticle
  product?: RadarProduct
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + 'T12:00:00').toLocaleDateString('pt-BR', {
    day: 'numeric',
    month: 'short',
  })
}

/** Wide layout — full-width card with image left, text right */
function WideCard({ article, product }: ArticleCardProps) {
  return (
    <article className="group col-span-full overflow-hidden rounded-2xl border border-border/50 bg-white transition-all duration-300 hover:shadow-lg hover:shadow-[#2d6a4f]/5">
      <div className="grid md:grid-cols-[1fr_1.2fr]">
        {/* Image */}
        <div className="relative aspect-[16/10] overflow-hidden bg-muted md:aspect-auto md:min-h-[280px]">
          <Image
            src={article.image}
            alt={article.title}
            fill
            className="object-cover transition-transform duration-500 group-hover:scale-[1.03]"
            sizes="(max-width: 768px) 100vw, 50vw"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent" />
        </div>

        {/* Content */}
        <div className="flex flex-col justify-center p-6 md:p-8">
          <div className="flex items-center gap-3">
            <PillarPill pillar={article.pillar} />
            <span className="text-[11px] text-muted-foreground">{formatDate(article.publishedAt)}</span>
          </div>
          <h3 className="mt-3 font-heading text-xl font-bold leading-snug text-foreground md:text-2xl">
            {article.title}
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{article.summary}</p>
          <p className="mt-3 text-[11px] text-muted-foreground/60">Fonte: {article.source}</p>
          {product && <ProductEmbed product={product} article={article} />}
        </div>
      </div>
    </article>
  )
}

/** Standard layout — vertical card with image on top */
function StandardCard({ article, product }: ArticleCardProps) {
  return (
    <article className="group flex flex-col overflow-hidden rounded-2xl border border-border/50 bg-white transition-all duration-300 hover:shadow-lg hover:shadow-[#2d6a4f]/5">
      {/* Image */}
      <div className="relative aspect-[16/10] overflow-hidden bg-muted">
        <Image
          src={article.image}
          alt={article.title}
          fill
          className="object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          sizes="(max-width: 768px) 100vw, 50vw"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent" />
        <div className="absolute left-3 top-3">
          <PillarPill pillar={article.pillar} />
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col p-5">
        <span className="text-[11px] text-muted-foreground">{formatDate(article.publishedAt)}</span>
        <h3 className="mt-2 font-heading text-lg font-bold leading-snug text-foreground">
          {article.title}
        </h3>
        <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">{article.summary}</p>
        <p className="mt-3 text-[11px] text-muted-foreground/60">Fonte: {article.source}</p>
        {product && <ProductEmbed product={product} article={article} />}
      </div>
    </article>
  )
}

/** Compact layout — text only, no image */
function CompactCard({ article, product }: ArticleCardProps) {
  return (
    <article className="group rounded-2xl border border-border/50 bg-white p-5 transition-all duration-300 hover:shadow-lg hover:shadow-[#2d6a4f]/5">
      <div className="flex items-center gap-3">
        <PillarPill pillar={article.pillar} />
        <span className="text-[11px] text-muted-foreground">{formatDate(article.publishedAt)}</span>
      </div>
      <h3 className="mt-3 font-heading text-lg font-bold leading-snug text-foreground">
        {article.title}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{article.summary}</p>
      <p className="mt-3 text-[11px] text-muted-foreground/60">Fonte: {article.source}</p>
      {product && <ProductEmbed product={product} article={article} />}
    </article>
  )
}

/** Main ArticleCard — dispatches to the correct layout variant */
export function ArticleCard({ article, product }: ArticleCardProps) {
  switch (article.layout) {
    case 'wide':
      return <WideCard article={article} product={product} />
    case 'compact':
      return <CompactCard article={article} product={product} />
    default:
      return <StandardCard article={article} product={product} />
  }
}
