import { useEffect, useRef } from 'react'

import { useBonarJsContext } from './useBonarJsContext'
import type { User } from '../../core/entities/User'

/** Options for {@link useRequireAuth}. */
export interface UseRequireAuthOptions {
  /**
   * Path to redirect to when unauthenticated.
   * @default '/login'
   */
  loginPath?: string

  /**
   * Called when the hook determines the user must be redirected.
   * Typically `router.replace(path)` from Next.js or your routing lib.
   *
   * If not provided, falls back to `window.location.replace(path)`.
   */
  redirect?: (path: string) => void
}

/** Return shape of {@link useRequireAuth}. */
export interface UseRequireAuthApi {
  /** The authenticated user, or null while loading / unauthenticated. */
  user: User | null
  /** Whether the auth state is still being resolved. */
  loading: boolean
}

/**
 * Auth guard hook. Redirects unauthenticated users to the configured login
 * path once the auth state has settled.
 *
 * Appends `?returnTo=<currentPath>` to the login URL so the login page
 * can redirect back after successful authentication.
 *
 * @example
 * ```tsx
 * const { user, loading } = useRequireAuth({ redirect: router.replace })
 * if (loading || !user) return <Loading />
 * ```
 */
export function useRequireAuth(options?: UseRequireAuthOptions): UseRequireAuthApi {
  const { user, loading } = useBonarJsContext()
  const { loginPath = '/login', redirect } = options ?? {}

  // Track whether we've already triggered a redirect to avoid duplicates
  const redirectedRef = useRef(false)

  useEffect(() => {
    if (loading) return
    if (user) {
      // User is authenticated — reset redirect guard
      redirectedRef.current = false
      return
    }

    // Unauthenticated
    if (redirectedRef.current) return
    redirectedRef.current = true

    const currentPath =
      typeof window !== 'undefined'
        ? window.location.pathname + window.location.search
        : '/'

    const returnTo = encodeURIComponent(currentPath)
    const destination = `${loginPath}?returnTo=${returnTo}`

    if (redirect) {
      redirect(destination)
    } else if (typeof window !== 'undefined') {
      window.location.replace(destination)
    }
  }, [loading, user, loginPath, redirect])

  return { user, loading }
}
