import { trackGtmEvent } from './googleTagManager'
import type { RadarArticle, RadarProduct } from '@/types/radar'

/** Fired when an individual article page loads */
export function trackArticleView(article: RadarArticle, editionWeek: string): void {
  trackGtmEvent('radar:article_view', {
    article_id: article.id,
    article_title: article.title,
    pillar: article.pillar,
    is_featured: article.featured,
    has_product: article.relatedProductIds.length > 0,
    edition_week: editionWeek,
    source: article.source,
  })
}

/** Fired when the ProductEmbed enters the viewport */
export function trackProductVisible(article: RadarArticle, product: RadarProduct): void {
  trackGtmEvent('radar:product_embed_visible', {
    article_id: article.id,
    product_id: product.id,
    product_title: product.title,
    product_price: product.pricing.price,
    product_category: product.category,
    pillar: article.pillar,
    creator_name: product.creator.name,
    platform: product.platform,
  })
}

/** Fired when user clicks the ProductEmbed (affiliate link) */
export function trackProductClick(article: RadarArticle, product: RadarProduct): void {
  trackGtmEvent('radar:product_embed_click', {
    article_id: article.id,
    product_id: product.id,
    product_title: product.title,
    product_price: product.pricing.price,
    product_category: product.category,
    pillar: article.pillar,
    creator_name: product.creator.name,
    platform: product.platform,
    link_url: product.links.salesPage,
  })
}

/** Fired when the /radar/ listing page loads */
export function trackListingView(editionWeek: string, articleCount: number): void {
  trackGtmEvent('radar:listing_view', {
    edition_week: editionWeek,
    article_count: articleCount,
  })
}

/** Fired when user clicks an article in the sidebar */
export function trackSidebarClick(
  clickedArticle: RadarArticle,
  sourceArticleId: string | null,
  sourcePage: 'listing' | 'article',
): void {
  trackGtmEvent('radar:sidebar_article_click', {
    clicked_article_id: clickedArticle.id,
    clicked_article_title: clickedArticle.title,
    clicked_pillar: clickedArticle.pillar,
    source_article_id: sourceArticleId,
    source_page: sourcePage,
  })
}
