'use client'

import { useCallback } from 'react'
import { ContactSection } from '@botanarede/ui-react'
import { useDynamicTable } from '@botanarede/bonarjs-sdk-alpha/react'

interface ContactSectionConnectedProps {
  [key: string]: unknown
  tableSlug?: string
  notifyEmail?: string
  tenantName?: string
}

export function ContactSectionConnected({
  tableSlug,
  notifyEmail,
  tenantName,
  ...rest
}: ContactSectionConnectedProps) {
  const { setItem } = useDynamicTable()

  const handleSubmit = useCallback(
    async (values: Record<string, string>) => {
      const createdAt = Date.now()
      const payload = { ...values, createdAt, type: 'simple_contact', source: tenantName ?? 'contact' }
      await setItem(tableSlug ?? 'contatos', payload, undefined, 'NONE')

      if (notifyEmail) {
        const text = Object.entries(values)
          .map(([k, v]) => `${k}: ${v}`)
          .join('\n')
        await setItem(
          'emails',
          {
            to: [notifyEmail],
            from: notifyEmail,
            message: {
              subject: `Novo contato - ${tenantName ?? 'Site'}`,
              text,
              html: text.replace(/\n/g, '<br/>'),
            },
            createdAt,
            type: 'simple_contact',
          },
          undefined,
          'EMAIL'
        )
      }

      if (typeof window !== 'undefined') {
        ;(window as any).dataLayer = (window as any).dataLayer || []
        ;(window as any).dataLayer.push({
          event: 'form_submission',
          form_type: 'simple_contact',
          form_name: tenantName ?? 'Contato',
        })
      }
    },
    [setItem, tableSlug, notifyEmail, tenantName]
  )

  return <ContactSection {...(rest as any)} onSubmit={handleSubmit} />
}
