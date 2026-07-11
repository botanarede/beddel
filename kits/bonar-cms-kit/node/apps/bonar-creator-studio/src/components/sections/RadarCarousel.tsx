'use client'

import Image from 'next/image'
import { useCallback, useEffect, useRef, useState } from 'react'
import { PillarPill } from '@/components/ui/PillarPill'
import type { RadarArticle } from '@/types/radar'

interface RadarCarouselProps {
  articles: RadarArticle[]
}

export function RadarCarousel({ articles }: RadarCarouselProps) {
  const [current, setCurrent] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const touchStartX = useRef(0)

  const total = articles.length

  const goTo = useCallback(
    (idx: number) => {
      setCurrent(((idx % total) + total) % total)
    },
    [total],
  )

  const next = useCallback(() => goTo(current + 1), [current, goTo])

  // Auto-rotate
  useEffect(() => {
    if (isPaused) return
    timerRef.current = setInterval(next, 6000)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [next, isPaused])

  // Touch handlers
  const onTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX
  }
  const onTouchEnd = (e: React.TouchEvent) => {
    const diff = touchStartX.current - e.changedTouches[0].clientX
    if (Math.abs(diff) > 50) {
      goTo(diff > 0 ? current + 1 : current - 1)
    }
  }

  return (
    <section className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
      {/* Section label */}
      <div className="mb-8 flex items-center gap-3">
        <div className="h-px flex-1 bg-gradient-to-r from-border to-transparent" />
        <span className="text-[11px] font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Em destaque
        </span>
        <div className="h-px flex-1 bg-gradient-to-l from-border to-transparent" />
      </div>

      {/* Carousel */}
      <div
        className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#f7f2ea] via-[#ede5d8] to-[#e8f5ee]"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {/* Slides */}
        <div
          className="flex transition-transform duration-700 ease-[cubic-bezier(0.25,0.1,0.25,1)]"
          style={{ transform: `translateX(-${current * 100}%)` }}
        >
          {articles.map((article) => (
            <div key={article.id} className="w-full flex-shrink-0">
              <div className="grid md:grid-cols-2">
                {/* Image */}
                <div className="relative aspect-[4/3] overflow-hidden md:aspect-auto md:min-h-[420px]">
                  <Image
                    src={article.image}
                    alt={article.title}
                    fill
                    className="object-cover"
                    sizes="(max-width: 768px) 100vw, 50vw"
                    priority={article === articles[0]}
                  />
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent to-[#f7f2ea]/30 md:bg-gradient-to-r md:from-transparent md:to-[#f7f2ea]/60" />
                </div>

                {/* Content */}
                <div className="flex flex-col justify-center p-8 md:p-12">
                  <PillarPill pillar={article.pillar} size="md" />
                  <h2 className="mt-4 font-heading text-2xl font-bold leading-snug text-[#1b4332] md:text-3xl lg:text-4xl">
                    {article.title}
                  </h2>
                  <p className="mt-4 text-sm leading-relaxed text-[#1b4332]/60 md:text-base">
                    {article.summary}
                  </p>
                  <p className="mt-4 text-[11px] text-[#1b4332]/40">
                    Fonte: {article.source}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Navigation arrows */}
        <button
          onClick={() => goTo(current - 1)}
          className="absolute left-3 top-1/2 z-10 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/80 text-[#1b4332] shadow-md backdrop-blur-sm transition-all hover:bg-white hover:shadow-lg md:left-5 md:h-12 md:w-12"
          aria-label="Anterior"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <button
          onClick={() => goTo(current + 1)}
          className="absolute right-3 top-1/2 z-10 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/80 text-[#1b4332] shadow-md backdrop-blur-sm transition-all hover:bg-white hover:shadow-lg md:right-5 md:h-12 md:w-12"
          aria-label="Próximo"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 18l6-6-6-6" />
          </svg>
        </button>

        {/* Dot indicators */}
        <div className="absolute bottom-4 left-1/2 z-10 flex -translate-x-1/2 gap-2 md:bottom-6">
          {articles.map((_, i) => (
            <button
              key={i}
              onClick={() => goTo(i)}
              className={`h-2 rounded-full transition-all duration-300 ${
                i === current
                  ? 'w-6 bg-[#2d6a4f]'
                  : 'w-2 bg-[#2d6a4f]/20 hover:bg-[#2d6a4f]/40'
              }`}
              aria-label={`Slide ${i + 1}`}
            />
          ))}
        </div>
      </div>
    </section>
  )
}
