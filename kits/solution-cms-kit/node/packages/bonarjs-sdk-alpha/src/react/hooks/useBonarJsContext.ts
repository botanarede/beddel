import { useContext } from 'react'

import { BonarJsContext, type BonarJsContextValue } from '../context/BonarJsContext'
import { BonarJsError } from '../../core/errors'

/**
 * Internal helper: returns the {@link BonarJsContextValue} or throws when
 * used outside a {@link BonarJsProvider}.
 */
export function useBonarJsContext(): BonarJsContextValue {
  const ctx = useContext(BonarJsContext)
  if (!ctx) {
    throw new BonarJsError(
      'react/missing-provider',
      'BonarJs hooks must be used inside <BonarJsProvider>.',
    )
  }
  return ctx
}
