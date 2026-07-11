import type { Metadata } from 'next'
import { Inter, Playfair_Display, Geist } from 'next/font/google'
import type { ReactNode } from 'react'

import { siteConfig } from '@/config/site.config'
import { loadRawTenantConfig } from '@/config/load-tenant'
import { generateThemeVars } from '@/lib/theme-vars'
import { GoogleTagManager } from '@/lib/googleTagManager'
import { ClientProviders } from './ClientProviders'

import './globals.css'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })
const playfair = Playfair_Display({ subsets: ['latin'], variable: '--font-playfair' })
const geist = Geist({ subsets: ['latin'], variable: '--font-geist' })

export const metadata: Metadata = {
  metadataBase: new URL(siteConfig.url || 'https://example.com'),
}

export default function RootLayout({ children }: { children: ReactNode }) {
  const gtmId = siteConfig.analytics.gtmId
  const tenant = loadRawTenantConfig()
  const themeCSS = generateThemeVars(siteConfig, tenant.designTokens)
  const bgImage = tenant.designTokens.backgroundImage

  return (
    <html lang="pt-BR">
      <head>
        <style dangerouslySetInnerHTML={{ __html: themeCSS }} />
      </head>
      <body className={`${inter.variable} ${playfair.variable} ${geist.variable} bg-white`}>
        {bgImage && (
          <div className="fixed inset-x-0 top-0 -z-10 h-screen">
            <div
              className="h-full w-full bg-cover bg-center bg-no-repeat"
              style={{ backgroundImage: `url('${bgImage}')` }}
            />
            <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-b from-transparent to-white" />
          </div>
        )}
        <GoogleTagManager gtmId={gtmId} type="script" />
        <GoogleTagManager gtmId={gtmId} type="noscript" />
        <ClientProviders>{children}</ClientProviders>
      </body>
    </html>
  )
}
