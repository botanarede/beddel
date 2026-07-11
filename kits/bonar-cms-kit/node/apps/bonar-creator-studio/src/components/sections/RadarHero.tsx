'use client'

import { useEffect, useRef, useState } from 'react'

function formatWeekLabel(): string {
  const now = new Date()
  const day = now.getDate()
  const month = now.toLocaleDateString('pt-BR', { month: 'long' })
  const year = now.getFullYear()
  return `Semana de ${day} de ${month} de ${year}`
}

export function RadarHero() {
  const ref = useRef<HTMLElement>(null)
  const [scrollY, setScrollY] = useState(0)

  useEffect(() => {
    const onScroll = () => {
      if (ref.current) {
        setScrollY(window.scrollY)
      }
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const parallax = scrollY * 0.3
  const opacity = Math.max(0, 1 - scrollY / 500)

  return (
    <section
      ref={ref}
      className="relative flex min-h-[70vh] items-center justify-center overflow-hidden bg-[#0a1f15] md:min-h-[80vh]"
    >
      {/* Background gradient layers */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 80% 60% at 50% 40%, rgba(45,106,79,0.4) 0%, rgba(10,31,21,0.95) 70%)',
          transform: `translateY(${parallax}px)`,
        }}
      />

      {/* Subtle grain texture overlay */}
      <div className="radar-grain absolute inset-0 opacity-[0.03]" />

      {/* Lotus watermark */}
      <div
        className="absolute right-[-5%] top-[10%] opacity-[0.04]"
        style={{ transform: `translateY(${parallax * 0.5}px)` }}
      >
        <img
          src="/images/lotus-transparent.png"
          alt=""
          className="h-[500px] w-auto md:h-[700px]"
        />
      </div>

      {/* Content */}
      <div
        className="relative z-10 mx-auto max-w-4xl px-6 text-center"
        style={{ opacity, transform: `translateY(${parallax * 0.15}px)` }}
      >
        {/* Overline */}
        <p className="text-xs font-medium uppercase tracking-[0.3em] text-[#95d5b2]/80">
          Inteligência &amp; Curadoria
        </p>

        {/* Title */}
        <h1 className="mt-4 font-heading text-5xl font-bold leading-[1.1] text-white md:text-7xl">
          Radar
          <span className="text-[#95d5b2]"> Prana</span>
        </h1>

        {/* Subtitle */}
        <p className="mx-auto mt-5 max-w-lg text-base leading-relaxed text-white/60 md:text-lg">
          Inteligência e curadoria para profissionais de bem-estar
        </p>

        {/* Week pill */}
        <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 backdrop-blur-sm">
          <span className="h-1.5 w-1.5 rounded-full bg-[#95d5b2] animate-pulse" />
          <span className="text-xs text-white/50">{formatWeekLabel()}</span>
        </div>

        {/* Scroll indicator */}
        <div className="mt-12 flex justify-center">
          <div className="flex flex-col items-center gap-2">
            <span className="text-[10px] uppercase tracking-widest text-white/30">Explorar</span>
            <div className="h-8 w-px animate-pulse bg-gradient-to-b from-white/30 to-transparent" />
          </div>
        </div>
      </div>

      {/* Bottom fade to white */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-white to-transparent" />
    </section>
  )
}
