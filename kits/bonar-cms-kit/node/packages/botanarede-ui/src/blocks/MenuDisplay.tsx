/**
 * MenuDisplay — paginated menu image viewer with front/back toggle
 * and fullscreen button.
 *
 * All interactions dispatch via callbacks (no direct router usage).
 */

'use client';

import { useState } from 'react';
import type { SectionComponentProps } from '../types';

export interface MenuPage {
  front: string;
  back?: string;
  label?: string;
}

interface MenuDisplayProps extends SectionComponentProps {
  pages?: MenuPage[];
  onFullscreen?: () => void;
}

export function MenuDisplay({ pages = [], onFullscreen }: MenuDisplayProps) {
  const [currentPage, setCurrentPage] = useState(0);
  const [showFront, setShowFront] = useState(true);

  if (pages.length === 0) {
    return (
      <section className="py-8 px-4 text-center text-gray-500">
        <p>Menu not available.</p>
      </section>
    );
  }

  const page = pages[currentPage];
  const currentImage = showFront ? page.front : (page.back ?? page.front);
  const hasBack = !!page.back;
  const totalPages = pages.length;

  return (
    <section className="py-8 px-4 md:px-8">
      <div className="flex flex-col items-center w-full max-w-lg mx-auto">
        {/* Controls: Front/Back toggle */}
        {hasBack && (
          <div className="mb-4 flex items-center justify-center">
            <button
              type="button"
              onClick={() => setShowFront(!showFront)}
              className="flex items-center gap-2 bg-green-700 text-white px-4 py-2 rounded-md hover:bg-green-800 transition-colors text-sm"
              aria-label={showFront ? 'Show back side' : 'Show front side'}
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
              {showFront ? 'Back' : 'Front'}
            </button>
          </div>
        )}

        {/* Menu Image */}
        <div
          className="relative cursor-pointer hover:opacity-90 transition-opacity"
          onClick={onFullscreen}
          role={onFullscreen ? 'button' : undefined}
          tabIndex={onFullscreen ? 0 : undefined}
          onKeyDown={(e) => {
            if (onFullscreen && (e.key === 'Enter' || e.key === ' ')) {
              e.preventDefault();
              onFullscreen();
            }
          }}
          aria-label={onFullscreen ? 'Open fullscreen view' : undefined}
        >
          <img
            src={currentImage}
            alt={page.label ?? `Menu page ${currentPage + 1} ${showFront ? 'front' : 'back'}`}
            className="max-w-full shadow-lg rounded-md"
            loading="lazy"
            decoding="async"
          />
          {/* Fullscreen overlay icon */}
          {onFullscreen && (
            <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity rounded-md bg-black/10">
              <div className="bg-black/60 text-white p-2 rounded-full">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" />
                </svg>
              </div>
            </div>
          )}
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="mt-4 flex items-center gap-4">
            <button
              type="button"
              onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
              disabled={currentPage === 0}
              className="px-3 py-1 rounded border text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-100 transition-colors"
              aria-label="Previous page"
            >
              ← Prev
            </button>
            <span className="text-sm text-gray-600">
              {currentPage + 1} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={currentPage === totalPages - 1}
              className="px-3 py-1 rounded border text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-100 transition-colors"
              aria-label="Next page"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
