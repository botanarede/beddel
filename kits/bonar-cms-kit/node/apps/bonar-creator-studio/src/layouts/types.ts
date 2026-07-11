import type { ComponentType, ReactNode } from 'react'
import type { NavigationConfig } from '@botanarede/schema'

export interface LayoutProps {
  children: ReactNode
  tenantId: string
  navigation: NavigationConfig
  siteConfig: {
    name: string
    branding: {
      logo: string
      logoWhite: string
      primaryColor: string
      accentColor: string
    }
    social: Record<string, string | undefined>
    email: string
    phone: string
  }
}

export type LayoutComponent = ComponentType<LayoutProps>
