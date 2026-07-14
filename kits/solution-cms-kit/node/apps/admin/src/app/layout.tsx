import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import type { ReactNode } from 'react'

import { ClientProviders } from './ClientProviders'
import { TenantProvider } from '@/lib/tenant-context'

import './globals.css'

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' })

export const metadata: Metadata = {
  title: 'Admin Panel',
  description: 'Botanarede centralized admin panel',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ClientProviders>
          <TenantProvider>{children}</TenantProvider>
        </ClientProviders>
      </body>
    </html>
  )
}
