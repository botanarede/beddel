import { createContext } from 'react'

import type { IAuthAdapter } from '../../core/interfaces/IAuthAdapter'
import type { IDatabaseAdapter } from '../../core/interfaces/IDatabaseAdapter'
import type { ICacheAdapter } from '../../core/interfaces/ICacheAdapter'
import type { IMailAdapter } from '../../core/interfaces/IMailAdapter'
import type { User } from '../../core/entities/User'

/** Adapter bundle supplied to {@link BonarJsProvider}. */
export interface BonarJsAdapters {
  auth: IAuthAdapter
  database: IDatabaseAdapter
  cache?: ICacheAdapter
  mail?: IMailAdapter
}

/** Value exposed by {@link BonarJsContext}. */
export interface BonarJsContextValue {
  adapters: BonarJsAdapters
  user: User | null
  loading: boolean
}

/**
 * React context populated by {@link BonarJsProvider}. Consumers should use
 * the provided hooks (`useAuth`, `useDynamicTable`, `useMail`, `useBonarJs`)
 * rather than reading the context directly.
 */
export const BonarJsContext = createContext<BonarJsContextValue | null>(null)
