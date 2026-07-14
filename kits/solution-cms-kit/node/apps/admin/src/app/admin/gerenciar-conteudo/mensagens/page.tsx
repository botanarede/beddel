'use client'

import { useEffect, useMemo, useState } from 'react'
import { useDynamicTable } from '@botanarede/bonarjs-sdk-alpha/react'

import { toDate } from '@/lib/timestamp'

interface EmailRow {
  id?: string
  to?: string
  from?: string
  type?: string
  createdAt?: number
  message?: { subject?: string; text?: string }
}

const FILTERS: { label: string; type: string | null }[] = [
  { label: 'All', type: null },
  { label: 'Contact', type: 'simple_contact' },
  { label: 'Birthday', type: 'birthday' },
  { label: 'Corporate', type: 'corporate' },
  { label: 'Reservation', type: 'reservation' },
]

export default function AdminMensagens() {
  const { getItems } = useDynamicTable()
  const [rows, setRows] = useState<EmailRow[]>([])
  const [filter, setFilter] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getItems<EmailRow>('emails', {
      orderBy: { field: 'createdAt', direction: 'desc' },
      limit: 200,
    })
      .then((items) => {
        if (active) setRows(items)
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

  const filtered = useMemo(
    () => (filter ? rows.filter((r) => r.type === filter) : rows),
    [filter, rows],
  )

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold">Messages</h1>

      <div className="mt-4 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setFilter(f.type)}
            className={`rounded-full border px-3 py-1 text-xs ${
              filter === f.type ? 'bg-foreground text-background' : ''
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="mt-8 text-sm text-muted-foreground">Loading...</p>
      ) : filtered.length === 0 ? (
        <p className="mt-8 text-sm text-muted-foreground">No results found</p>
      ) : (
        <ul className="mt-8 divide-y rounded-lg border bg-background text-sm">
          {filtered.map((row) => (
            <li key={row.id ?? row.createdAt} className="px-4 py-3">
              <div className="flex items-center justify-between">
                <p className="font-medium">
                  {row.message?.subject ?? row.type ?? 'Message'}
                </p>
                <span className="text-xs text-muted-foreground">
                  {row.createdAt
                    ? (toDate(row.createdAt)?.toLocaleString('en-US') ?? '')
                    : ''}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {row.from ?? '—'} — {row.type ?? '—'}
              </p>
              {row.message?.text ? (
                <p className="mt-2 whitespace-pre-wrap">{row.message.text}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
