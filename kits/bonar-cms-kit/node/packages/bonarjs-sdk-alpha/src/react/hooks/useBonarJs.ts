import { useAuth, type UseAuthApi } from './useAuth'
import { useDynamicTable, type UseDynamicTableApi } from './useDynamicTable'
import { useMail, type UseMailApi } from './useMail'

/** Return shape of {@link useBonarJs}. */
export interface UseBonarJsApi {
  auth: UseAuthApi
  dynamicTable: UseDynamicTableApi
  mail: UseMailApi
}

/** Convenience hook exposing all sub-hooks in one object. */
export function useBonarJs(): UseBonarJsApi {
  return {
    auth: useAuth(),
    dynamicTable: useDynamicTable(),
    mail: useMail(),
  }
}
