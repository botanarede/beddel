import { useCallback, useMemo, useState } from 'react'

import { SendMail } from '../../core/useCases/mail/SendMail'
import type { MailPayload } from '../../core/types'
import { BonarJsError } from '../../core/errors'
import { useBonarJsContext } from './useBonarJsContext'

/** Return shape of {@link useMail}. */
export interface UseMailApi {
  loading: boolean
  error: string | null
  sendMail: (payload: MailPayload) => Promise<void>
}

/** React binding for the mail use cases. */
export function useMail(): UseMailApi {
  const { adapters } = useBonarJsContext()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sendUseCase = useMemo(() => {
    if (!adapters.mail) return null
    return new SendMail(adapters.mail)
  }, [adapters.mail])

  const sendMail = useCallback(
    async (payload: MailPayload) => {
      if (!sendUseCase) {
        throw new BonarJsError(
          'react/missing-mail-adapter',
          'useMail requires a mail adapter on BonarJsProvider.',
        )
      }
      setLoading(true)
      setError(null)
      try {
        await sendUseCase.execute(payload)
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
        throw err
      } finally {
        setLoading(false)
      }
    },
    [sendUseCase],
  )

  return { loading, error, sendMail }
}
