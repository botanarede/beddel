import { useCallback, useMemo, useState } from 'react'

import { DeleteItemById } from '../../core/useCases/dynamicTable/DeleteItemById'
import { GetItemById } from '../../core/useCases/dynamicTable/GetItemById'
import { GetItemChildById } from '../../core/useCases/dynamicTable/GetItemChildById'
import { GetItems } from '../../core/useCases/dynamicTable/GetItems'
import { SetItem } from '../../core/useCases/dynamicTable/SetItem'
import type { EventType, QueryOptions } from '../../core/types'
import { useBonarJsContext } from './useBonarJsContext'

/** Return shape of {@link useDynamicTable}. */
export interface UseDynamicTableApi {
  loading: boolean
  error: string | null
  getItems: <T = unknown>(table: string, options?: QueryOptions) => Promise<T[]>
  getItemById: <T = unknown>(table: string, id: string) => Promise<T | null>
  getItemChildById: <T = unknown>(
    table: string,
    itemId: string,
    childName: string,
    childId: string,
  ) => Promise<T | null>
  setItem: <T = unknown>(
    table: string,
    data: object,
    id?: string,
    events?: EventType,
  ) => Promise<T>
  deleteItemById: (table: string, id: string) => Promise<{ success: true }>
}

/** React binding for the dynamic-table use cases. */
export function useDynamicTable(): UseDynamicTableApi {
  const { adapters } = useBonarJsContext()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const getItemsUseCase = useMemo(() => new GetItems(adapters.database), [adapters.database])
  const getItemByIdUseCase = useMemo(
    () => new GetItemById(adapters.database),
    [adapters.database],
  )
  const getItemChildByIdUseCase = useMemo(
    () => new GetItemChildById(adapters.database),
    [adapters.database],
  )
  const setItemUseCase = useMemo(
    () => new SetItem(adapters.database, adapters.cache),
    [adapters.database, adapters.cache],
  )
  const deleteItemByIdUseCase = useMemo(
    () => new DeleteItemById(adapters.database, adapters.cache),
    [adapters.database, adapters.cache],
  )

  const wrap = useCallback(async <T>(fn: () => Promise<T>): Promise<T> => {
    setLoading(true)
    setError(null)
    try {
      return await fn()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const getItems = useCallback(
    <T = unknown>(table: string, options?: QueryOptions) =>
      wrap(() => getItemsUseCase.execute<T & { archived?: boolean }>(table, options) as Promise<T[]>),
    [wrap, getItemsUseCase],
  )
  const getItemById = useCallback(
    <T = unknown>(table: string, id: string) =>
      wrap(() => getItemByIdUseCase.execute<T>(table, id)),
    [wrap, getItemByIdUseCase],
  )
  const getItemChildById = useCallback(
    <T = unknown>(
      table: string,
      itemId: string,
      childName: string,
      childId: string,
    ) =>
      wrap(() =>
        getItemChildByIdUseCase.execute<T>(table, itemId, childName, childId),
      ),
    [wrap, getItemChildByIdUseCase],
  )
  const setItem = useCallback(
    <T = unknown>(
      table: string,
      data: object,
      id?: string,
      events?: EventType,
    ) => wrap(() => setItemUseCase.execute<T>(table, data, id, events)),
    [wrap, setItemUseCase],
  )
  const deleteItemById = useCallback(
    (table: string, id: string) =>
      wrap(() => deleteItemByIdUseCase.execute(table, id)),
    [wrap, deleteItemByIdUseCase],
  )

  return {
    loading,
    error,
    getItems,
    getItemById,
    getItemChildById,
    setItem,
    deleteItemById,
  }
}
