'use client'

import Link from 'next/link'

import { useTenant } from '@/lib/tenant-context'

export default function ContentHub() {
  const { tenantConfig } = useTenant()
  const features = tenantConfig?.features

  const links = [
    {
      label: 'Events',
      href: '/admin/gerenciar-conteudo/agenda',
      enabled: features?.events !== false,
    },
    {
      label: 'Contact',
      href: '/admin/gerenciar-conteudo/contato',
      enabled: features?.contact !== false,
    },
    {
      label: 'Messages',
      href: '/admin/gerenciar-conteudo/mensagens',
      enabled: true,
    },
    {
      label: 'Forms',
      href: '/admin/gerenciar-conteudo/formularios',
      enabled: true,
    },
  ].filter((l) => l.enabled)

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-semibold">Content Management</h1>
      <ul className="mt-8 grid gap-4 sm:grid-cols-2">
        {links.map((l) => (
          <li key={l.href}>
            <Link
              href={l.href}
              className="block rounded-lg border bg-background p-6 text-sm font-medium transition-shadow hover:shadow-md"
            >
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
