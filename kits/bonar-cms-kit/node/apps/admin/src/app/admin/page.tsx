'use client'

import { useEffect, useState } from 'react'
import { useDynamicTable } from '@botanarede/bonarjs-sdk-alpha/react'
import Link from 'next/link'

import { useTenant } from '@/lib/tenant-context'
import { toDate } from '@/lib/timestamp'

interface EmailRow {
  id?: string
  to?: string
  from?: string
  type?: string
  createdAt?: number
  message?: { subject?: string; text?: string }
}

export default function AdminDashboard() {
  const { getItems } = useDynamicTable()
  const { tenantConfig, tenantId } = useTenant()
  const [rows, setRows] = useState<EmailRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getItems<EmailRow>('emails', {
      orderBy: { field: 'createdAt', direction: 'desc' },
      limit: 20,
    })
      .then((items) => {
        if (!active) return
        setRows(items)
      })
      .catch(() => {
        if (active) setRows([])
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [getItems])

  const tenantName = tenantConfig?.metadata?.name ?? tenantId ?? 'Unknown'

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-10">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Welcome back — {tenantName}
        </p>
      </div>

      {/* Quick actions */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Link
          href="/admin/gerenciar-conteudo/agenda"
          className="rounded-lg border bg-background p-4 text-sm font-medium transition-shadow hover:shadow-md"
        >
          Manage Events
        </Link>
        <Link
          href="/admin/gerenciar-conteudo/contato"
          className="rounded-lg border bg-background p-4 text-sm font-medium transition-shadow hover:shadow-md"
        >
          Manage Contact
        </Link>
        <Link
          href="/admin/gerenciar-conteudo/mensagens"
          className="rounded-lg border bg-background p-4 text-sm font-medium transition-shadow hover:shadow-md"
        >
          View Messages
        </Link>
      </div>

      {/* Recent messages */}
      <section className="rounded-lg border bg-background p-4">
        <h2 className="mb-4 text-lg font-semibold">Recent Messages</h2>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No results found</p>
        ) : (
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b">
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">From</th>
                <th className="px-3 py-2 text-left">Subject</th>
                <th className="px-3 py-2 text-left">Date</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id ?? row.createdAt} className="border-b">
                  <td className="px-3 py-2">{row.type ?? '—'}</td>
                  <td className="px-3 py-2">{row.from ?? '—'}</td>
                  <td className="px-3 py-2">
                    {row.message?.subject ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {row.createdAt
                      ? (toDate(row.createdAt)?.toLocaleString('en-US') ??
                          '')
                      : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
