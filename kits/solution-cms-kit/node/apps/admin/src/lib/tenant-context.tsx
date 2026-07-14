'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import type { TenantConfig } from '@botanarede/schema'

const STORAGE_KEY = 'cms_selected_tenant'

interface TenantSummary {
  id: string
  name: string
  fileName: string
}

interface TenantContextValue {
  tenantId: string | null
  tenantConfig: TenantConfig | null
  tenants: TenantSummary[]
  selectTenant: (id: string) => void
  loading: boolean
}

const TenantContext = createContext<TenantContextValue>({
  tenantId: null,
  tenantConfig: null,
  tenants: [],
  selectTenant: () => {},
  loading: true,
})

export function TenantProvider({ children }: { children: ReactNode }) {
  const [tenants, setTenants] = useState<TenantSummary[]>([])
  const [tenantId, setTenantId] = useState<string | null>(null)
  const [tenantConfig, setTenantConfig] = useState<TenantConfig | null>(null)
  const [loading, setLoading] = useState(true)

  // Load available tenants on mount
  useEffect(() => {
    async function init() {
      try {
        const res = await fetch('/api/tenants')
        if (res.ok) {
          const data: TenantSummary[] = await res.json()
          setTenants(data)
        }
      } catch {
        // Tenants will remain empty
      }

      // Restore persisted selection
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        setTenantId(stored)
      }
      setLoading(false)
    }
    init()
  }, [])

  // Load full config when tenantId changes
  useEffect(() => {
    if (!tenantId) {
      setTenantConfig(null)
      return
    }

    let active = true
    async function loadConfig() {
      try {
        const res = await fetch(`/api/tenants/${tenantId}`)
        if (res.ok && active) {
          const data = await res.json()
          setTenantConfig(data)
        }
      } catch {
        if (active) setTenantConfig(null)
      }
    }
    loadConfig()
    return () => {
      active = false
    }
  }, [tenantId])

  const selectTenant = useCallback((id: string) => {
    localStorage.setItem(STORAGE_KEY, id)
    setTenantId(id)
  }, [])

  return (
    <TenantContext.Provider
      value={{ tenantId, tenantConfig, tenants, selectTenant, loading }}
    >
      {children}
    </TenantContext.Provider>
  )
}

export function useTenant(): TenantContextValue {
  return useContext(TenantContext)
}
