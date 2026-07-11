/**
 * PhotoGallery — sectioned image gallery with "show more" expansion.
 *
 * Each section has a heading and a responsive CSS grid of thumbnails.
 * Thumbnail click dispatches onImageClick callback (app wires to lightbox).
 */

'use client';

import { useState } from 'react';
import type { SectionComponentProps } from '../types';

export interface GalleryImageItem {
  src: string;
  alt: string;
  thumb?: string;
}

export interface GallerySection {
  title: string;
  images: GalleryImageItem[];
}

interface PhotoGalleryProps extends SectionComponentProps {
  sections?: GallerySection[];
  initialVisibleCount?: number;
  onImageClick?: (image: GalleryImageItem, index: number) => void;
}

function GallerySectionBlock({
  section,
  initialVisibleCount,
  onImageClick,
}: {
  section: GallerySection;
  initialVisibleCount: number;
  onImageClick?: (image: GalleryImageItem, index: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const visibleImages = expanded
    ? section.images
    : section.images.slice(0, initialVisibleCount);
  const hasMore = section.images.length > initialVisibleCount;

  return (
    <div className="mb-10">
      <h3 className="text-xl font-semibold text-gray-800 mb-4">{section.title}</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {visibleImages.map((image, index) => (
          <button
            key={index}
            type="button"
            onClick={() => onImageClick?.(image, index)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onImageClick?.(image, index);
              }
            }}
            className="relative aspect-square rounded-lg overflow-hidden group focus:outline-none focus:ring-2 focus:ring-green-500"
            aria-label={image.alt}
            tabIndex={0}
          >
            <img
              src={image.thumb ?? image.src}
              alt={image.alt}
              className="w-full h-full object-cover transition-transform group-hover:scale-105"
              loading="lazy"
              decoding="async"
            />
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />
          </button>
        ))}
      </div>
      {hasMore && !expanded && (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="px-6 py-2 text-sm font-medium text-green-700 border border-green-700 rounded-md hover:bg-green-50 transition-colors"
          >
            Show more ({section.images.length - initialVisibleCount} more)
          </button>
        </div>
      )}
    </div>
  );
}

export function PhotoGallery({
  sections,
  data,
  initialVisibleCount = 6,
  onImageClick,
}: PhotoGalleryProps) {
  // Prefer sections prop; fall back to data from dataBinding
  const gallerySections: GallerySection[] = sections ?? (data as GallerySection[]) ?? [];

  if (gallerySections.length === 0) {
    return (
      <section className="py-8 px-4 text-center text-gray-500">
        <p>No photos available.</p>
      </section>
    );
  }

  return (
    <section className="py-8 px-4 md:px-8">
      {gallerySections.map((section, index) => (
        <GallerySectionBlock
          key={index}
          section={section}
          initialVisibleCount={initialVisibleCount}
          onImageClick={onImageClick}
        />
      ))}
    </section>
  );
}
