'use client';

import { useState, useEffect, useCallback } from 'react';
import type { SectionComponentProps } from '../types';

export interface MediaItem {
  title: string;
  poster: string;
  videoUrl?: string;
}

interface MediaGalleryProps extends SectionComponentProps {
  items?: MediaItem[];
  heading?: string;
}

export function MediaGallery({ items = [], heading }: MediaGalleryProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const closeModal = useCallback(() => setActiveIndex(null), []);

  useEffect(() => {
    if (activeIndex === null) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeModal();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [activeIndex, closeModal]);

  const activeItem = activeIndex !== null ? items[activeIndex] : null;

  return (
    <section className="py-16 px-4">
      {heading && (
        <h2 className="text-3xl font-bold text-center text-foreground mb-10">
          {heading}
        </h2>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
        {items.map((item, idx) => (
          <button
            key={idx}
            type="button"
            aria-label={`Reproduzir ${item.title}`}
            onClick={() => setActiveIndex(idx)}
            className="group relative aspect-video rounded-xl overflow-hidden focus:outline-none focus:ring-2 focus:ring-white/50"
          >
            {/* Poster background */}
            <div
              className="absolute inset-0 bg-cover bg-center transition-transform duration-300 group-hover:scale-105"
              style={{ backgroundImage: `url(${item.poster})` }}
            />

            {/* Dark overlay on hover */}
            <div className="absolute inset-0 bg-black/20 group-hover:bg-black/40 transition-colors" />

            {/* Play icon */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-16 h-16 rounded-full bg-white/20 backdrop-blur flex items-center justify-center transition-transform group-hover:scale-110">
                <svg
                  className="w-6 h-6 text-white ml-1"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path d="M8 5v14l11-7z" />
                </svg>
              </div>
            </div>

            {/* Title */}
            <div className="absolute bottom-0 inset-x-0 p-3 bg-gradient-to-t from-black/60 to-transparent">
              <span className="text-white text-sm font-medium">{item.title}</span>
            </div>
          </button>
        ))}
      </div>

      {/* Modal */}
      {activeItem && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur flex items-center justify-center p-4"
          onClick={closeModal}
          role="dialog"
          aria-modal="true"
          aria-label={activeItem.title}
        >
          {/* Close button */}
          <button
            type="button"
            aria-label="Fechar"
            onClick={closeModal}
            className="absolute top-4 right-4 text-white hover:text-white/80 z-10"
          >
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          {/* Content */}
          <div
            className="w-full max-w-4xl aspect-video"
            onClick={(e) => e.stopPropagation()}
          >
            {activeItem.videoUrl ? (
              <iframe
                src={activeItem.videoUrl}
                title={activeItem.title}
                className="w-full h-full rounded-lg"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            ) : (
              <div className="w-full h-full rounded-lg bg-neutral-900 flex items-center justify-center">
                <p className="text-white/70 text-lg">Vídeo em breve</p>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
