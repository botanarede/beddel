'use client'

import { useEffect, useRef, useState } from 'react'
import { PillarPill } from '@/components/ui/PillarPill'
import type { RadarArticle } from '@/types/radar'
import { articlePath } from '@/types/radar'
import { trackSidebarClick } from '@/lib/radar-tracking'

interface RadarSidebarProps {
  articles: RadarArticle[]
  activeId: string | null
  /** Edition week slug, e.g. "2026-w18". Required for building article links. */
  editionWeek: string
  /** Where the sidebar is rendered — used for tracking context. Default: 'listing' */
  sourcePage?: 'listing' | 'article'
}

export function RadarSidebar({ articles, activeId, editionWeek, sourcePage = 'listing' }: RadarSidebarProps) {
  const [open, setOpen] = useState(false)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  // Scroll active article into view on mount
  useEffect(() => {
    if (!activeId || !scrollContainerRef.current) return
    const timer = setTimeout(() => {
      const el = scrollContainerRef.current?.querySelector(`[data-article-id="${activeId}"]`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }, 300) // small delay to let the sidebar render
    return () => clearTimeout(timer)
  }, [activeId])

  // Lock body scroll when mobile menu is open
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

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <>
      {/* Mobile hamburger button — fixed top-right */}
      <button
        onClick={() => setOpen(true)}
        className="fixed right-4 top-4 z-[60] flex h-10 w-10 items-center justify-center rounded-xl bg-[#2d6a4f] text-white shadow-lg transition-all hover:bg-[#1b4332] md:hidden"
        aria-label="Abrir menu"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M3 6h18M3 12h18M3 18h18" />
        </svg>
      </button>

      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-[70] bg-black/50 backdrop-blur-sm md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar — desktop: fixed left, mobile: fullscreen overlay */}
      <aside
        className={`
          fixed top-0 z-[80] flex h-full flex-col bg-[#0a1f15] text-white
          transition-transform duration-300 ease-[cubic-bezier(0.25,0.1,0.25,1)]
          left-0 right-0 w-full
          ${open ? 'translate-x-0' : '-translate-x-full'}
          md:left-0 md:right-auto md:w-[340px] md:translate-x-0
          lg:w-[380px]
        `}
      >
        {/* Close button — mobile only */}
        <button
          onClick={() => setOpen(false)}
          className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-white transition-colors hover:bg-white/20 md:hidden"
          aria-label="Fechar menu"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>

        {/* Header — logo centered */}
        <div className="flex flex-col items-center border-b border-white/10 px-6 pb-6 pt-8">
          <a href="/radar/">
            <img
              src="/images/marca-prana.webp"
              alt="Demo Brand"
              className="h-12 w-auto brightness-0 invert lg:h-14"
            />
          </a>
          <div className="mt-4 flex items-center gap-2">
            <a href="/radar/" className="rounded-full bg-[#2d6a4f] px-3 py-1 text-[11px] font-semibold tracking-wider transition-colors hover:bg-[#2d6a4f]/80">
              RADAR
            </a>
          </div>
          <p className="mt-2 text-center text-[11px] leading-relaxed text-white/40">
            Inteligência e curadoria para<br />profissionais de bem-estar
          </p>
        </div>

        {/* Navigation links */}
        <div className="mb-3 mt-4 px-6">
          <a
            href="/"
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-white/50 transition-colors hover:bg-white/5 hover:text-white/80"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 18l-6-6 6-6" />
            </svg>
            Voltar para Home
          </a>
        </div>

        {/* Article list — scrollable */}
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-4 pb-6 scrollbar-thin">
          <p className="mb-3 px-2 text-[10px] font-medium uppercase tracking-[0.2em] text-white/30">
            Artigos desta semana
          </p>

          <nav className="flex flex-col gap-1.5">
            {articles.map((article) => {
              const isActive = article.id === activeId
              const href = articlePath(editionWeek, article.id)
              return (
                <a
                  key={article.id}
                  href={href}
                  data-article-id={article.id}
                  onClick={() => trackSidebarClick(article, activeId, sourcePage)}
                  className={`group block rounded-xl px-2.5 py-2.5 transition-all duration-200 ${
                    isActive
                      ? 'bg-[#2d6a4f]/60 shadow-lg shadow-[#2d6a4f]/20'
                      : 'hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {/* Article thumbnail */}
                    <div className="relative h-12 w-12 flex-shrink-0 overflow-hidden rounded-lg bg-white/10">
                      <img
                        src={article.image}
                        alt=""
                        className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-110"
                      />
                      {isActive && (
                        <div className="absolute inset-0 border-2 border-[#95d5b2] rounded-lg" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3
                        className={`font-sans text-[13px] font-medium leading-snug transition-colors ${
                          isActive ? 'text-white' : 'text-white/70 group-hover:text-white/90'
                        }`}
                      >
                        {article.title}
                      </h3>
                      <div className="mt-1.5 flex items-center gap-2">
                        <PillarPill pillar={article.pillar} size="sm" />
                        {article.featured && (
                          <span className="text-[9px] font-medium uppercase tracking-wider text-[#95d5b2]/60">
                            Destaque
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </a>
              )
            })}
          </nav>
        </div>

        {/* Footer */}
        <div className="border-t border-white/10 px-6 py-4">
          <p className="text-center text-[10px] text-white/25">
            © {new Date().getFullYear()} Demo Brand
          </p>
        </div>
      </aside>
    </>
  )
}
