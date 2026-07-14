'use client'

import type { ReactNode } from 'react'

/** Centered card wrapper used by /login. */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-muted/40 px-6 py-16">
      <div className="mb-8 text-2xl font-bold tracking-tight">
        Botanarede Admin
      </div>
      <div className="w-full max-w-md rounded-lg border bg-background p-8 shadow-sm">
        {children}
      </div>
    </main>
  )
}
