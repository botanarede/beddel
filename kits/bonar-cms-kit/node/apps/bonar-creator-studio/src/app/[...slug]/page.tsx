/**
 * Catch-all route for schema-driven pages.
 *
 * Reads the tenant JSON, matches the URL to a declared page,
 * resolves the layout and sections via the component registry,
 * and renders the full page.
 *
 * Also handles data-driven sub-routes (e.g., /radar/[weekDate]/[slug])
 * by matching route patterns declared in the page definition.
 */

import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { loadRawTenantConfig } from '@/config/load-tenant'
import { siteConfig } from '@/config/site.config'
import { resolveComponent } from '@/registry'
import { resolveLayout } from '@/layouts'
import { resolveDataBindings, type ResolvedSection } from '@/renderer/resolve-data'
import type { PageDefinition } from '@botanarede/schema'

// Import article data for generating static params for article detail pages
import { loadCachedTable } from '@/lib/load-cache'
import type { RadarArticle } from '@/types/radar'
import { weekDateSlug } from '@/types/radar'

const articles = loadCachedTable<RadarArticle>('noticias')
const editionWeek = articles.length > 0
  ? weekDateSlug(articles[0].publishedAt)
  : '2026-w18'

export async function generateStaticParams() {
  const tenant = loadRawTenantConfig()
  const pages = Object.values(tenant.pages) as PageDefinition[]

  const pageParams = pages
    .filter((p) => p.visibility !== 'admin')
    .filter((p) => p.route !== '/') // home is handled by app/page.tsx
    .map((p) => ({
      slug: p.route.split('/').filter(Boolean),
    }))

  // Generate article detail page params from noticias data
  const articleParams = articles.map((a) => ({
    slug: ['radar', editionWeek, a.id],
  }))

  return [...pageParams, ...articleParams]
}

interface Props {
  params: Promise<{ slug: string[] }>
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params
  const route = '/' + slug.join('/')
  const tenant = loadRawTenantConfig()
  const pages = Object.values(tenant.pages) as PageDefinition[]
  const pageDef = pages.find((p) => p.route === route)

  if (pageDef) {
    const title = pageDef.title
    const description = pageDef.description ?? siteConfig.description
    const ogImage = pageDef.ogImage ?? siteConfig.branding.ogImage
    const canonical = `${siteConfig.url}${route}`

    return {
      title,
      description,
      openGraph: {
        title,
        description,
        images: [{ url: ogImage, width: 1200, height: 630, alt: title }],
        url: canonical,
      },
      alternates: { canonical },
    }
  }

  // Check if this is a radar article detail page
  if (slug.length === 3 && slug[0] === 'radar') {
    const articleSlug = slug[2]
    const article = articles.find((a) => a.id === articleSlug)
    if (article) {
      return {
        title: `${article.title} — Radar Prana`,
        description: article.summary,
        openGraph: {
          title: article.title,
          description: article.summary,
          type: 'article',
          locale: 'pt_BR',
          images: [{ url: article.image, width: 800, height: 500, alt: article.title }],
        },
      }
    }
  }

  return {}
}

export default async function CatchAllPage({ params }: Props) {
  const { slug } = await params
  const route = '/' + slug.join('/')
  const tenant = loadRawTenantConfig()

  const pages = Object.values(tenant.pages) as PageDefinition[]
  const pageDef = pages.find((p) => p.route === route)

  // Schema-driven page rendering
  if (pageDef) {
    const Layout = resolveLayout(pageDef.layoutRef)
    const resolvedSections = await resolveDataBindings(
      pageDef.sections,
      tenant.metadata.id,
    )

    return (
      <Layout
        tenantId={tenant.metadata.id}
        navigation={tenant.navigation}
        siteConfig={siteConfig}
      >
        {resolvedSections.map((section: ResolvedSection, i: number) => {
          const Component = resolveComponent(section.type)
          if (!Component) {
            console.warn(`[renderer] Unknown component: ${section.type}`)
            return null
          }

          // Check feature gate
          if (section.featureGate) {
            const features = tenant.features ?? {}
            if (!features[section.featureGate]) return null
          }

          const element = (
            <Component
              {...section.props}
              data={section.resolvedData}
              tenantId={tenant.metadata.id}
              siteConfig={siteConfig}
            />
          )

          return section.id ? (
            <section key={section.id} id={section.id} className="scroll-mt-20">
              {element}
            </section>
          ) : (
            <div key={`${section.type}-${i}`}>{element}</div>
          )
        })}
      </Layout>
    )
  }

  // Radar article detail page (data-driven)
  if (slug.length === 3 && slug[0] === 'radar') {
    const articleSlug = slug[2]
    const article = articles.find((a) => a.id === articleSlug)

    if (article) {
      // Dynamically import the article page component
      const { RadarArticlePage } = await import('@/components/sections/RadarArticlePage')
      const { loadCachedTable: loadProducts } = await import('@/lib/load-cache')
      const products = loadProducts<import('@/types/radar').RadarProduct>('produtos')

      const product = article.relatedProductIds[0]
        ? products.find((p) => p.id === article.relatedProductIds[0])
        : undefined

      return (
        <RadarArticlePage
          article={article}
          product={product}
          allArticles={articles}
          editionWeek={editionWeek}
        />
      )
    }
  }

  return notFound()
}
