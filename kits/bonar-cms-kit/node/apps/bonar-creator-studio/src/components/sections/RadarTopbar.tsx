'use client'

import { useEffect, useState } from 'react'

export function RadarTopbar() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={`fixed left-0 right-0 top-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'border-b border-border/40 bg-white/80 shadow-sm backdrop-blur-xl'
          : 'bg-transparent'
      }`}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 md:h-20 md:px-8">
        {/* Logo + Radar label */}
        <a href="/" className="flex items-center gap-3">
          <img
            src="/images/marca-prana.webp"
            alt="Demo Brand"
            className={`h-10 w-auto transition-all duration-300 md:h-12 ${
              scrolled ? '' : 'brightness-0 invert drop-shadow-[0_2px_8px_rgba(0,0,0,0.3)]'
            }`}
          />
        </a>

        {/* Nav */}
        <nav className="flex items-center gap-6">
          <a
            href="/"
            className={`text-xs font-medium tracking-wide transition-colors ${
              scrolled ? 'text-muted-foreground hover:text-foreground' : 'text-white/70 hover:text-white'
            }`}
          >
            Home
          </a>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              scrolled
                ? 'bg-[#2d6a4f] text-white'
                : 'bg-white/15 text-white backdrop-blur-sm'
            }`}
          >
            Radar
          </span>
        </nav>
      </div>
    </header>
  )
}
