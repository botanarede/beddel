'use client'

import { useEffect, useState } from 'react'
import { useDynamicTable } from '@botanarede/bonarjs-sdk-alpha/react'

interface FormRow {
  id?: string
  name: string
  description?: string
  fields: Array<{ name: string; label: string; type: string }>
}

export default function AdminForms() {
  const { getItems } = useDynamicTable()
  const [rows, setRows] = useState<FormRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getItems<FormRow>('formularios')
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
      <h1 className="text-2xl font-semibold">Forms</h1>
      {loading ? (
        <p className="mt-6 text-sm text-muted-foreground">Loading...</p>
      ) : rows.length === 0 ? (
        <p className="mt-6 text-sm text-muted-foreground">No results found</p>
      ) : (
        <ul className="mt-8 divide-y rounded-lg border bg-background text-sm">
          {rows.map((row) => (
            <li key={row.id ?? row.name} className="px-4 py-3">
              <p className="font-medium">{row.name}</p>
              <p className="text-xs text-muted-foreground">
                {row.fields.length} fields
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
