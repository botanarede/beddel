'use client'

import {
  CalendarRange,
  FileText,
  Home,
  LayoutGrid,
  LogOut,
  Mail,
  MessageSquare,
  Users,
} from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { ReactNode } from 'react'
import { useAuth } from '@botanarede/bonarjs-sdk-alpha/react'
import { useRequireAuth } from '@botanarede/bonarjs-sdk-alpha/react'

import { useTenant } from '@/lib/tenant-context'
import { cn } from '@/lib/utils'

interface AdminNavItem {
  label: string
  href: string
  Icon: typeof Home
  enabled: boolean
}

function buildAdminNav(features?: Record<string, boolean>): AdminNavItem[] {
  return [
    { label: 'Dashboard', href: '/admin', Icon: Home, enabled: true },
    {
      label: 'Content Management',
      href: '/admin/gerenciar-conteudo',
      Icon: LayoutGrid,
      enabled: true,
    },
    {
      label: 'Events',
      href: '/admin/gerenciar-conteudo/agenda',
      Icon: CalendarRange,
      enabled: features?.events !== false,
    },
    {
      label: 'Messages',
      href: '/admin/gerenciar-conteudo/mensagens',
      Icon: Mail,
      enabled: true,
    },
    {
      label: 'Forms',
      href: '/admin/gerenciar-conteudo/formularios',
      Icon: MessageSquare,
      enabled: true,
    },
    {
      label: 'Reports',
      href: '/admin/relatorios',
      Icon: FileText,
      enabled: features?.reports === true,
    },
  ].filter((item) => item.enabled)
}

/**
 * Wraps authenticated admin routes. Redirects to /login if no user is
 * present after the auth adapter finishes hydrating.
 *
 * Uses `useRequireAuth` from the SDK which appends `?returnTo=` to the
 * login URL so users are redirected back after authentication.
 */
export function AdminLayout({ children }: { children: ReactNode }) {
  const router = useRouter()
  const { user, loading } = useRequireAuth({
    loginPath: '/login',
    redirect: (path) => router.replace(path),
  })
  const { signOut } = useAuth()
  const { tenantId, tenantConfig, tenants, selectTenant } = useTenant()

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading...
      </div>
    )
  }

  const nav = buildAdminNav(tenantConfig?.features)
  const tenantName = tenantConfig?.metadata?.name ?? tenantId ?? 'No tenant'

  return (
    <div className="flex min-h-screen bg-muted/30">
      <aside className="hidden w-64 flex-col border-r bg-background px-4 py-6 md:flex">
        <div className="mb-4 px-3">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Admin Panel
          </p>
        </div>

        {/* Tenant selector */}
        <div className="mb-6 px-3">
          <label
            htmlFor="tenant-select"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Tenant
          </label>
          <select
            id="tenant-select"
            value={tenantId ?? ''}
            onChange={(e) => {
              if (e.target.value) selectTenant(e.target.value)
            }}
            className="w-full rounded-md border bg-background px-2 py-1.5 text-sm"
          >
            <option value="" disabled>
              Select tenant...
            </option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          {tenantId && (
            <p className="mt-1 truncate text-xs text-muted-foreground">
              {tenantName}
            </p>
          )}
        </div>

        <nav className="flex flex-1 flex-col gap-1 text-sm">
          {nav.map(({ label, href, Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
        </nav>

        <button
          type="button"
          onClick={async () => {
            await fetch('/api/logout', { method: 'GET' })
            void signOut()
          }}
          className="mt-4 flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <LogOut size={18} />
          Logout
        </button>
      </aside>
      <div className="flex-1 px-4 py-6 md:px-10 md:py-10">{children}</div>
    </div>
  )
}
