'use client'

import type { ReactNode } from 'react'

import { AdminLayout } from '@/components/layouts/AdminLayout'

export default function AdminRouteLayout({ children }: { children: ReactNode }) {
  return <AdminLayout>{children}</AdminLayout>
}
