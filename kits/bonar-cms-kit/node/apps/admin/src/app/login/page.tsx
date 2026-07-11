'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import { useAuth } from '@botanarede/bonarjs-sdk-alpha/react'
import { LoginStatus } from '@botanarede/bonarjs-sdk-alpha'
import { getAuth } from 'firebase/auth'

import { AuthLayout } from '@/components/layouts/AuthLayout'

export default function LoginPage() {
  const { user, loading, signInEmailPassword } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const returnTo = searchParams.get('returnTo') ?? '/'

  useEffect(() => {
    if (!loading && user) router.replace(returnTo)
  }, [loading, user, router, returnTo])

  const submit = async (evt: React.FormEvent) => {
    evt.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)

    try {
      // 1. Sign in via Firebase client SDK
      const result = await signInEmailPassword(email, password)
      if (result.message !== LoginStatus.SUCCESS) {
        setError(result.message)
        setBusy(false)
        return
      }

      // 2. Get the ID token from the signed-in user
      const auth = getAuth()
      const idToken = await auth.currentUser?.getIdToken()
      if (!idToken) {
        setError('Failed to get authentication token')
        setBusy(false)
        return
      }

      // 3. Exchange ID token for httpOnly session cookie via server
      const res = await fetch('/api/login', {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${idToken}`,
        },
      })

      if (!res.ok) {
        setError('Failed to create server session')
        setBusy(false)
        return
      }

      // 4. Session cookie is now set — redirect to intended destination
      router.replace(returnTo)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      console.error('[login] auth error:', err)
      setError(msg)
    }
    setBusy(false)
  }

  return (
    <AuthLayout>
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <form onSubmit={submit} className="mt-6 flex flex-col gap-4 text-sm">
        <label className="flex flex-col gap-1">
          <span className="font-medium">Email</span>
          <input
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-md border px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-medium">Password</span>
          <input
            required
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-md border px-3 py-2"
          />
        </label>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-[color:var(--brand-primary)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </AuthLayout>
  )
}
