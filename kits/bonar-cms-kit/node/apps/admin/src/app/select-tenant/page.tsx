'use client'

import { useRouter } from 'next/navigation'
import { useRequireAuth } from '@botanarede/bonarjs-sdk-alpha/react'

import { useTenant } from '@/lib/tenant-context'

export default function SelectTenantPage() {
  const router = useRouter()
  const { user, loading: authLoading } = useRequireAuth({
    loginPath: '/login',
    redirect: (path) => router.replace(path),
  })
  const { tenants, selectTenant, loading: tenantLoading } = useTenant()

  const handleSelect = (id: string) => {
    selectTenant(id)
    router.push('/admin')
  }

  if (authLoading || tenantLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading...
      </div>
    )
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-muted/40 px-6 py-16">
      <h1 className="mb-2 text-2xl font-semibold">Select Tenant</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        Choose a tenant to manage
      </p>

      {tenants.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No tenants found. Add tenant JSON files to the tenants/ directory.
        </p>
      ) : (
        <div className="grid w-full max-w-2xl gap-4 sm:grid-cols-2">
          {tenants.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => handleSelect(t.id)}
              className="rounded-lg border bg-background p-6 text-left shadow-sm transition-shadow hover:shadow-md"
            >
              <p className="text-lg font-medium">{t.name}</p>
              <p className="mt-1 text-xs text-muted-foreground">{t.id}</p>
            </button>
          ))}
        </div>
      )}
    </main>
  )
}
