/**
 * LunchSection — preview image with optional video play button and gallery strip.
 *
 * Renders a preview image with rounded corners, an optional play button overlay
 * when videoUrl is provided, and a horizontal scrollable gallery strip.
 */

'use client';

import type { SectionComponentProps } from '../types';

export interface GalleryImage {
  src: string;
  alt: string;
}

interface LunchSectionProps extends SectionComponentProps {
  heading?: string;
  previewImage?: string;
  videoUrl?: string;
  galleryImages?: GalleryImage[];
  onPlayVideo?: () => void;
}

export function LunchSection({
  heading = 'Weekend Lunch',
  previewImage,
  videoUrl,
  galleryImages = [],
  onPlayVideo,
}: LunchSectionProps) {
  return (
    <section className="py-12 px-4 md:px-8 bg-green-50">
      {heading && (
        <h2 className="text-2xl md:text-3xl font-bold text-green-800 text-center mb-8">
          {heading}
        </h2>
      )}

      <div className="max-w-4xl mx-auto">
        {/* Preview Image with optional Play Button */}
        {previewImage && (
          <div className="relative rounded-xl overflow-hidden shadow-lg mb-6">
            <img
              src={previewImage}
              alt={heading}
              className="w-full h-auto object-cover rounded-xl"
              loading="lazy"
              decoding="async"
            />
            {videoUrl && (
              <button
                type="button"
                onClick={onPlayVideo}
                className="absolute inset-0 flex items-center justify-center bg-black/30 hover:bg-black/40 transition-colors"
                aria-label="Play video"
              >
                <div className="w-16 h-16 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
                  <svg
                    className="h-8 w-8 text-green-700 ml-1"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
              </button>
            )}
          </div>
        )}

        {/* Gallery Strip */}
        {galleryImages.length > 0 && (
          <div className="overflow-x-auto pb-2">
            <div className="flex gap-3 min-w-max">
              {galleryImages.map((image, index) => (
                <div
                  key={index}
                  className="flex-shrink-0 w-24 h-24 rounded-lg overflow-hidden"
                >
                  <img
                    src={image.src}
                    alt={image.alt}
                    className="w-full h-full object-cover"
                    loading="lazy"
                    decoding="async"
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
