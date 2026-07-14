/**
 * Home page — fully schema-driven.
 *
 * The tenant JSON declares the home page (route: "/") in `pages`,
 * and the page is rendered via the component registry and layout system.
 */

import type { Metadata } from 'next'
import { loadRawTenantConfig } from '@/config/load-tenant'
import { siteConfig } from '@/config/site.config'
import { resolveComponent } from '@/registry'
import { resolveLayout } from '@/layouts'
import { resolveDataBindings, type ResolvedSection } from '@/renderer/resolve-data'
import type { PageDefinition } from '@botanarede/schema'

export async function generateMetadata(): Promise<Metadata> {
  const tenant = loadRawTenantConfig()
  const pages = Object.values(tenant.pages) as PageDefinition[]
  const homeDef = pages.find((p) => p.route === '/')

  const title = homeDef?.title ?? `${siteConfig.name} — ${siteConfig.tagline}`
  const description = homeDef?.description ?? siteConfig.description
  const ogImage = homeDef?.ogImage ?? siteConfig.branding.ogImage
  const canonical = siteConfig.url

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      siteName: siteConfig.name,
      locale: 'pt_BR',
      type: 'website',
      url: canonical,
      images: [{ url: ogImage, width: 1200, height: 630, alt: siteConfig.name }],
    },
    icons: { icon: siteConfig.branding.favicon },
    robots: { index: true, follow: true },
    alternates: { canonical },
  }
}

export default async function HomePage() {
  const tenant = loadRawTenantConfig()
  const pages = Object.values(tenant.pages) as PageDefinition[]
  const homeDef = pages.find((p) => p.route === '/')

  if (!homeDef) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">No home page configured.</p>
      </main>
    )
  }

  const Layout = resolveLayout(homeDef.layoutRef)
  const resolvedSections = await resolveDataBindings(
    homeDef.sections,
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
        if (!Component) return null

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
