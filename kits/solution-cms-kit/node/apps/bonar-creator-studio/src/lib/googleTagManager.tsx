'use client'

import { useEffect } from 'react'

export interface GoogleTagManagerProps {
  /** GTM container id, e.g. `GTM-XXXXXX`. Empty string disables the injection. */
  gtmId?: string
  type: 'script' | 'noscript'
}

/** Ambient type augmentation so we can push to `dataLayer` without `any`. */
declare global {
  interface Window {
    dataLayer?: Array<Record<string, unknown>>
  }
}

/**
 * Minimal Google Tag Manager bootstrap. Renders either the async script tag
 * (head) or the `<noscript>` iframe (body) depending on `type`. Noop when
 * `gtmId` is empty — callers can unconditionally mount the component and
 * control activation from `siteConfig.analytics.gtmId`.
 */
export function GoogleTagManager({ gtmId, type }: GoogleTagManagerProps) {
  useEffect(() => {
    if (!gtmId || type !== 'script') return
    if (typeof window === 'undefined') return

    window.dataLayer = window.dataLayer ?? []
    window.dataLayer.push({ 'gtm.start': Date.now(), event: 'gtm.js' })

    const first = document.getElementsByTagName('script')[0]
    if (!first?.parentNode) return
    const script = document.createElement('script')
    script.async = true
    script.src = `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(gtmId)}`
    first.parentNode.insertBefore(script, first)
  }, [gtmId, type])

  if (!gtmId || type === 'script') return null

  return (
    <noscript>
      <iframe
        src={`https://www.googletagmanager.com/ns.html?id=${encodeURIComponent(gtmId)}`}
        height="0"
        width="0"
        style={{ display: 'none', visibility: 'hidden' }}
        title="Google Tag Manager"
      />
    </noscript>
  )
}

/** Fire a GTM event from client code. Safe no-op on server. */
export function trackGtmEvent(event: string, payload: Record<string, unknown> = {}): void {
  if (typeof window === 'undefined') return
  window.dataLayer = window.dataLayer ?? []
  window.dataLayer.push({ event, ...payload })
}
