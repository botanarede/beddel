'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

import { useTenant } from '@/lib/tenant-context'

/**
 * Root page: redirects to /admin if a tenant is selected,
 * otherwise to /select-tenant.
 */
export default function RootPage() {
  const { tenantId, loading } = useTenant()
  const router = useRouter()

  useEffect(() => {
    if (loading) return
    if (tenantId) {
      router.replace('/admin')
    } else {
      router.replace('/select-tenant')
    }
  }, [tenantId, loading, router])

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
      Loading...
    </div>
  )
}
