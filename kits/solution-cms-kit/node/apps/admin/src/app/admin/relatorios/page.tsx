'use client'

import { useTenant } from '@/lib/tenant-context'

export default function AdminReports() {
  const { tenantConfig } = useTenant()

  if (!tenantConfig?.features?.reports) {
    return (
      <div className="mx-auto max-w-5xl">
        <h1 className="text-2xl font-semibold">Reports</h1>
        <div className="mt-4 inline-block rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">
          Coming soon
        </div>
        <p className="mt-4 text-sm text-muted-foreground">
          Weekly analytics reports will be available here.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold">Reports</h1>
      <p className="mt-4 text-sm text-muted-foreground">
        Weekly analytics reports will be available here.
      </p>
    </div>
  )
}
