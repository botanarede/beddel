'use client'

import { useState } from 'react'

interface AlbumItem {
  title: string
  date: string
  link: string
  image: string
  align?: 'top' | 'middle' | 'bottom'
}

interface PhotoGalleryCasasavanaProps {
  albums?: AlbumItem[]
  initialVisibleCount?: number
  [key: string]: unknown
}

/**
 * Photo gallery for Casa Savana — displays event albums as card grid.
 * Each card links to an external Google Drive folder with photos.
 * Albums are sorted by date (most recent first).
 */
export function PhotoGalleryCasasavana({
  albums = [],
  initialVisibleCount = 12,
}: PhotoGalleryCasasavanaProps) {
  const [showAll, setShowAll] = useState(false)

  // Sort albums by date (DD/MM/YYYY) — most recent first
  const sorted = [...albums].sort((a, b) => {
    const parseDate = (d: string) => {
      const [day, month, year] = d.split('/').map(Number)
      return new Date(year, month - 1, day).getTime()
    }
    return parseDate(b.date) - parseDate(a.date)
  })

  const visible = showAll ? sorted : sorted.slice(0, initialVisibleCount)
  const hasMore = sorted.length > initialVisibleCount

  if (albums.length === 0) {
    return (
      <section className="py-8 px-4 text-center text-gray-500">
        <p>Nenhuma foto disponível no momento.</p>
      </section>
    )
  }

  return (
    <section className="py-8 px-4 md:px-8">
      <h1 className="mb-8 text-center text-3xl font-bold text-gray-800">Fotos</h1>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((album, index) => (
          <article
            key={`${album.title}-${album.date}-${index}`}
            className="group overflow-hidden rounded-lg border-2 border-gray-100 bg-white shadow-sm transition-all hover:border-green-200 hover:shadow-md"
          >
            {/* Image */}
            <div className="relative h-48 overflow-hidden bg-gray-100">
              <img
                src={album.image}
                alt={`${album.title} — ${album.date}`}
                loading={index < 6 ? 'eager' : 'lazy'}
                decoding="async"
                className={`absolute min-h-full min-w-full object-cover transition-transform group-hover:scale-105 ${
                  album.align === 'top'
                    ? 'left-1/2 top-0 -translate-x-1/2'
                    : album.align === 'bottom'
                      ? 'bottom-0 left-1/2 -translate-x-1/2'
                      : 'left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2'
                }`}
              />
            </div>

            {/* Content */}
            <div className="p-4">
              <h3 className="text-lg font-semibold text-green-800">{album.title}</h3>
              <div className="mt-2 flex items-center gap-2 text-sm text-gray-600">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0" aria-hidden="true">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
                <span>{album.date}</span>
              </div>
            </div>

            {/* Action */}
            <div className="px-4 pb-4">
              <a
                href={album.link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex w-full items-center justify-center gap-2 rounded-md border border-green-800 px-4 py-2 text-sm font-medium text-green-800 transition-colors hover:bg-green-50"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                Visualizar
              </a>
            </div>
          </article>
        ))}
      </div>

      {/* Show more button */}
      {hasMore && !showAll && (
        <div className="mt-8 text-center">
          <button
            type="button"
            onClick={() => setShowAll(true)}
            className="rounded-md border border-green-700 px-6 py-2.5 text-sm font-medium text-green-700 transition-colors hover:bg-green-50"
          >
            Ver todos ({sorted.length - initialVisibleCount} mais)
          </button>
        </div>
      )}
    </section>
  )
}
