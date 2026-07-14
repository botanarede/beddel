'use client'

import Image from 'next/image'
import { useEffect, useRef, useState } from 'react'

export function HeroSection() {
  const ref = useRef<HTMLElement>(null)
  const [t, setT] = useState(0)

  useEffect(() => {
    let ticking = false
    const onScroll = () => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        if (!ref.current) {
          ticking = false
          return
        }
        const rect = ref.current.getBoundingClientRect()
        const h = ref.current.offsetHeight
        setT(Math.min(Math.max(-rect.top / h, 0), 1))
        ticking = false
      })
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
  const fade = Math.min(Math.max((ease - 0.15) / 0.25, 0), 1)
  const heroOut = Math.min(Math.max((ease - 0.4) / 0.2, 0), 1)
  const barIn = Math.min(Math.max((ease - 0.45) / 0.2, 0), 1)
  const logoO = 1 - ease * 0.9
  const logoY = ease * -30

  return (
    <>
      {/* Hero scroll section */}
      <section ref={ref} className="relative h-[130vh]">
        <div className="sticky top-0 h-screen w-full overflow-hidden bg-[#0a1f15]">
          {/* Scene 1 */}
          <div
            className="absolute inset-0 will-change-transform"
            style={{
              opacity: (1 - fade * 0.5) * (1 - heroOut),
              transform: `translateY(${ease * -30}px) scale(1.03)`,
            }}
          >
            <Image src="/images/hero-1-desktop.webp" alt="" fill priority
              className="hidden object-cover md:block" sizes="100vw" />
            <Image src="/images/hero-1-mobile.webp" alt="" fill priority
              className="object-cover md:hidden" sizes="100vw" />
          </div>

          {/* Scene 2 */}
          <div
            className="absolute inset-0 will-change-transform"
            style={{
              opacity: fade * (1 - heroOut),
              transform: `translateY(${ease * -15}px) scale(1.03)`,
            }}
          >
            <Image src="/images/hero-2-desktop.webp" alt="" fill
              className="hidden object-cover md:block" sizes="100vw" />
            <Image src="/images/hero-2-mobile.webp" alt="" fill
              className="object-cover md:hidden" sizes="100vw" />
          </div>

          {/* Hero logo — white centered */}
          <div
            className="pointer-events-none absolute inset-0 flex items-center justify-center will-change-transform"
            style={{ opacity: logoO, transform: `translateY(${logoY}px)` }}
          >
            <img
              src="/images/marca-prana.webp"
              alt="Site Logo"
              className="h-auto w-[60vw] max-w-[520px] brightness-0 invert drop-shadow-[0_4px_30px_rgba(0,0,0,0.4)] md:w-[26vw]"
            />
          </div>

          {/* Scroll hint */}
          <div
            className="absolute bottom-10 left-1/2 -translate-x-1/2"
            style={{ opacity: Math.max(0, 1 - t * 4) }}
          >
            <div className="h-10 w-px animate-pulse bg-white/30" />
          </div>
        </div>
      </section>

      {/* Fixed topbar — no button, just logo + lotus accent */}
      <div
        className="fixed left-0 right-0 top-0 z-50 will-change-transform"
        style={{
          opacity: barIn,
          transform: `translateY(${(1 - barIn) * -100}%)`,
          pointerEvents: barIn > 0.3 ? 'auto' : 'none',
        }}
      >
        <div
          className="relative h-20 overflow-hidden backdrop-blur-md md:h-24"
          style={{
            background: 'linear-gradient(130deg, rgba(247,242,234,0.92) 0%, rgba(237,229,216,0.88) 35%, rgba(90,154,120,0.85) 60%, rgba(26,58,42,0.9) 100%)',
          }}
        >
          {/* Lotus flower — right side, transparent bg */}
          <div className="absolute -right-4 -top-6 bottom-0 flex w-28 items-center justify-center md:-right-2 md:-top-4 md:w-40">
            <img
              src="/images/lotus-transparent.png"
              alt=""
              className="h-24 w-auto opacity-60 md:h-32 md:opacity-50"
            />
          </div>

          {/* Bottom border */}
          <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-[#d4c9b8]/50 to-transparent" />

          {/* Logo — bigger, left aligned */}
          <div className="relative z-10 mx-auto flex h-full max-w-6xl items-center justify-between px-5 md:px-8">
            <img
              src="/images/marca-prana.webp"
              alt="Site Logo"
              className="h-14 w-auto md:h-[68px]"
            />

            {/* Radar button */}
            <a
              href="/radar/"
              className="mr-12 flex items-center gap-1.5 rounded-full bg-[#1b4332]/90 px-3.5 py-1.5 text-[11px] font-semibold tracking-wider text-white shadow-md backdrop-blur-sm transition-all hover:bg-[#2d6a4f] hover:shadow-lg md:mr-20 md:px-4 md:py-2 md:text-xs"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="opacity-80">
                <circle cx="12" cy="12" r="10" />
                <circle cx="12" cy="12" r="6" />
                <circle cx="12" cy="12" r="2" />
                <line x1="12" y1="2" x2="12" y2="4" />
                <line x1="12" y1="20" x2="12" y2="22" />
                <line x1="2" y1="12" x2="4" y2="12" />
                <line x1="20" y1="12" x2="22" y2="12" />
              </svg>
              RADAR
            </a>
          </div>
        </div>
      </div>
    </>
  )
}
