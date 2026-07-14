'use client'

import { useEffect, useState, type ReactNode } from 'react'

interface StickyHeaderProps {
  children: ReactNode
  transparent?: boolean
}

/**
 * Sticky header that optionally starts transparent and gains a
 * background on scroll. Used for single-page (hash nav) sites like
 * Terreiro de Bamba. For multi-page sites, it renders as a normal
 * opaque sticky header.
 */
export function StickyHeader({ children, transparent = false }: StickyHeaderProps) {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    if (!transparent) return
    const onScroll = () => setScrolled(window.scrollY > 80)
    onScroll() // initial check
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [transparent])

  const baseClasses = 'sticky top-0 z-50 transition-all duration-300'
  const bgClasses = !transparent || scrolled
    ? 'bg-background/95 backdrop-blur border-b border-border'
    : 'bg-transparent border-b border-transparent'

  return (
    <header className={`${baseClasses} ${bgClasses}`}>
      {children}
    </header>
  )
}
