'use client'

import { useState, useEffect } from 'react'

interface NavItem {
  label: string
  type: string
  route?: string
  href?: string
  hash?: string
}

interface MobileNavProps {
  items: NavItem[]
  siteName: string
}

/**
 * Mobile hamburger navigation — slides in from the right.
 * Only renders the toggle button and panel on screens < md.
 */
export function MobileNav({ items, siteName }: MobileNavProps) {
  const [open, setOpen] = useState(false)

  // Close on escape key
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  // Prevent body scroll when menu is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  const getHref = (item: NavItem): string => {
    if (item.type === 'route') return item.route ?? '/'
    if (item.type === 'external') return item.href ?? '#'
    if (item.type === 'hash') return item.hash ?? '#'
    return '#'
  }

  return (
    <div className="md:hidden">
      {/* Hamburger button */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="relative z-50 flex h-10 w-10 items-center justify-center rounded-md text-gray-700 hover:bg-gray-100 transition-colors"
        aria-label={open ? 'Close menu' : 'Open menu'}
        aria-expanded={open}
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          {open ? (
            <>
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </>
          ) : (
            <>
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </>
          )}
        </svg>
      </button>

      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Slide-in panel */}
      <nav
        className={`fixed right-0 top-0 z-40 h-full w-64 transform bg-white shadow-xl transition-transform duration-300 ease-in-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
        aria-label="Mobile navigation"
      >
        <div className="flex h-16 items-center border-b px-5">
          <span className="text-sm font-semibold text-gray-800">{siteName}</span>
        </div>
        <ul className="flex flex-col gap-1 p-4">
          {items.map((item) => (
            <li key={item.label}>
              <a
                href={getHref(item)}
                onClick={() => setOpen(false)}
                className="block rounded-md px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-[color:var(--brand-primary)] transition-colors"
                {...(item.type === 'external' ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
              >
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
