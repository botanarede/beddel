import type { LayoutProps } from './types'
import { StickyHeader } from '@/components/StickyHeader'
import { MobileNav } from '@/components/MobileNav'

/**
 * Public layout — header with logo + navigation, main content, footer.
 * Used for all standard public-facing pages.
 *
 * When navigation contains hash items (single-page mode), the header
 * starts transparent and gains a background on scroll.
 */
export function PublicLayout({ children, navigation, siteConfig }: LayoutProps) {
  const mainMenu = navigation.menus['main']
  const navItems = mainMenu?.items ?? []
  const hasHashNav = navItems.some((item) => item.type === 'hash')

  const socialLinks = siteConfig.social ?? {}

  return (
    <>
      <StickyHeader transparent={hasHashNav}>
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 md:h-20 md:px-8">
          <a href="/" aria-label={siteConfig.name}>
            <img
              src={siteConfig.branding.logo}
              alt={siteConfig.name}
              className="h-10 w-auto md:h-14"
            />
          </a>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-6" aria-label="Main navigation">
            {navItems.map((item) => {
              if (item.type === 'route') {
                return (
                  <a
                    key={item.route}
                    href={item.route}
                    className="text-sm font-medium text-foreground/80 transition-colors hover:text-[color:var(--brand-primary)]"
                  >
                    {item.label}
                  </a>
                )
              }
              if (item.type === 'external') {
                return (
                  <a
                    key={item.href}
                    href={item.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-foreground/80 transition-colors hover:text-[color:var(--brand-primary)]"
                  >
                    {item.label}
                  </a>
                )
              }
              if (item.type === 'hash') {
                return (
                  <a
                    key={item.hash}
                    href={item.hash}
                    className="text-sm font-medium text-foreground/80 transition-colors hover:text-[color:var(--brand-primary)]"
                  >
                    {item.label}
                  </a>
                )
              }
              return null
            })}
          </nav>

          {/* Mobile hamburger */}
          <MobileNav items={navItems} siteName={siteConfig.name} />
        </div>
      </StickyHeader>

      <main>{children}</main>

      <footer className="border-t bg-gray-50 py-10">
        <div className="mx-auto max-w-6xl px-6">
          <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
            {/* Brand + tagline */}
            <div>
              <img
                src={siteConfig.branding.logo}
                alt={siteConfig.name}
                className="h-10 w-auto mb-3"
              />
              <p className="text-sm text-gray-600">{siteConfig.name}</p>
            </div>

            {/* Contact info */}
            <div>
              <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gray-700">
                Contato
              </h4>
              <ul className="space-y-2 text-sm text-gray-600">
                {siteConfig.email && (
                  <li>
                    <a href={`mailto:${siteConfig.email}`} className="hover:text-gray-900 transition-colors">
                      {siteConfig.email}
                    </a>
                  </li>
                )}
                {siteConfig.phone && (
                  <li>
                    <a href={`tel:${siteConfig.phone}`} className="hover:text-gray-900 transition-colors">
                      {siteConfig.phone}
                    </a>
                  </li>
                )}
              </ul>
            </div>

            {/* Social links */}
            <div>
              <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gray-700">
                Redes Sociais
              </h4>
              <div className="flex gap-4">
                {socialLinks.instagram && (
                  <a
                    href={socialLinks.instagram}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-500 hover:text-gray-900 transition-colors"
                    aria-label="Instagram"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
                    </svg>
                  </a>
                )}
                {socialLinks.facebook && (
                  <a
                    href={socialLinks.facebook}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-500 hover:text-gray-900 transition-colors"
                    aria-label="Facebook"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
                    </svg>
                  </a>
                )}
                {socialLinks.tiktok && (
                  <a
                    href={socialLinks.tiktok}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-500 hover:text-gray-900 transition-colors"
                    aria-label="TikTok"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                      <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.88 2.89 2.89 0 0 1-2.88-2.88 2.89 2.89 0 0 1 2.88-2.88c.28 0 .56.04.82.11v-3.5a6.37 6.37 0 0 0-.82-.05A6.34 6.34 0 0 0 3.15 15.7a6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.34-6.34V8.98a8.21 8.21 0 0 0 4.76 1.52V7.06a4.84 4.84 0 0 1-1-.37z" />
                    </svg>
                  </a>
                )}
              </div>
            </div>
          </div>

          {/* Copyright bar */}
          <div className="mt-8 border-t pt-6 text-center text-xs text-gray-500">
            © {new Date().getFullYear()} {siteConfig.name}. Todos os direitos reservados.
          </div>
        </div>
      </footer>
    </>
  )
}
