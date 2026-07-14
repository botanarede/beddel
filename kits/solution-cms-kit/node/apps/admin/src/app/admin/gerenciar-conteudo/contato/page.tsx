'use client'

import { useEffect, useState } from 'react'
import { useDynamicTable } from '@botanarede/bonarjs-sdk-alpha/react'

import { useTenant } from '@/lib/tenant-context'

interface MetadataRow {
  id?: string
  key?: string
  value?: string
  [k: string]: unknown
}

export default function AdminContato() {
  const { getItems, setItem } = useDynamicTable()
  const { tenantConfig } = useTenant()
  const [rows, setRows] = useState<MetadataRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getItems<MetadataRow>('metadata')
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

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-semibold">Contact</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Manage contact page metadata for{' '}
        {tenantConfig?.metadata?.name ?? 'this tenant'}
      </p>

      {loading ? (
        <p className="mt-8 text-sm text-muted-foreground">Loading...</p>
      ) : rows.length === 0 ? (
        <p className="mt-8 text-sm text-muted-foreground">
          No contact metadata found. Contact page content is managed via the
          tenant configuration file.
        </p>
      ) : (
        <ul className="mt-8 divide-y rounded-lg border bg-background text-sm">
          {rows.map((row) => (
            <li key={row.id ?? row.key} className="px-4 py-3">
              <p className="font-medium">{row.key ?? row.id ?? 'Entry'}</p>
              <p className="text-xs text-muted-foreground">
                {typeof row.value === 'string'
                  ? row.value
                  : JSON.stringify(row)}
              </p>
            </li>
          ))}
        </ul>
      )}

      {tenantConfig?.features?.corporateEvents && (
        <section className="mt-10">
          <h2 className="text-lg font-semibold">Corporate Events</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Corporate event inquiries are enabled for this tenant. Messages of
            type &quot;corporate&quot; will appear in the Messages section.
          </p>
        </section>
      )}
    </div>
  )
}
