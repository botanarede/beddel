import { ArticleCard } from '@/components/ui/ArticleCard'
import type { RadarArticle, RadarProduct } from '@/types/radar'

interface RadarGridProps {
  articles: RadarArticle[]
  products: RadarProduct[]
}

export function RadarGrid({ articles, products }: RadarGridProps) {
  const productMap = new Map(products.map((p) => [p.id, p]))

  function getProduct(article: RadarArticle): RadarProduct | undefined {
    if (article.relatedProductIds.length === 0) return undefined
    return productMap.get(article.relatedProductIds[0])
  }

  return (
    <section className="mx-auto max-w-6xl px-5 pb-16 md:px-8">
      {/* Section header */}
      <div className="mb-10">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-[#2d6a4f]">
          Curadoria
        </p>
        <h2 className="mt-2 font-heading text-2xl font-bold text-foreground md:text-3xl">
          Destaques da Semana
        </h2>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          Artigos selecionados com dados verificados sobre o mercado de bem-estar brasileiro.
        </p>
      </div>

      {/* Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {articles.map((article) => (
          <ArticleCard
            key={article.id}
            article={article}
            product={getProduct(article)}
          />
        ))}
      </div>
    </section>
  )
}
