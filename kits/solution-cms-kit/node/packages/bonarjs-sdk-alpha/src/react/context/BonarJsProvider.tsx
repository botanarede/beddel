import { useEffect, useMemo, useState, type ReactNode } from 'react'

import type { User } from '../../core/entities/User'
import {
  BonarJsContext,
  type BonarJsAdapters,
  type BonarJsContextValue,
} from './BonarJsContext'

/** Props accepted by {@link BonarJsProvider}. */
export interface BonarJsProviderProps {
  adapters: BonarJsAdapters
  children: ReactNode
}

/**
 * Top-level provider that wires the SDK adapters into the React tree and
 * keeps the auth state in sync via `IAuthAdapter.onAuthStateChanged`.
 */
export function BonarJsProvider({
  adapters,
  children,
}: BonarJsProviderProps): JSX.Element {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    adapters.auth
      .getCurrentUser()
      .then((u) => {
        if (mounted) setUser(u)
      })
      .catch(() => {
        /* ignore */
      })

    const unsubscribe = adapters.auth.onAuthStateChanged((u) => {
      if (!mounted) return
      setUser(u)
      setLoading(false)
    })

    return () => {
      mounted = false
      unsubscribe()
    }
  }, [adapters.auth])

  const value = useMemo<BonarJsContextValue>(
    () => ({ adapters, user, loading }),
    [adapters, user, loading],
  )

  return <BonarJsContext.Provider value={value}>{children}</BonarJsContext.Provider>
}
