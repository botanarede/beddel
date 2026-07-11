/**
 * HeroCarousel — full-width image carousel with autoplay, navigation arrows,
 * and dot indicators.
 *
 * Uses picture element for responsive desktop/mobile sources.
 * Autoplay pauses on user interaction and resumes after a delay.
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { SectionComponentProps } from '../types';

export interface CarouselSlide {
  desktopImage: string;
  mobileImage?: string;
  alt: string;
  caption?: string;
}

interface HeroCarouselOverlay {
  logo?: string;
  logoAlt?: string;
  title?: string;
  tagline?: string;
  ctaLabel?: string;
  ctaHref?: string;
}

interface HeroCarouselProps extends SectionComponentProps {
  slides?: CarouselSlide[];
  autoplay?: boolean;
  interval?: number;
  onSlideChange?: (index: number) => void;
  overlay?: HeroCarouselOverlay;
  height?: string;
}

export function HeroCarousel({
  slides = [],
  autoplay = true,
  interval = 5000,
  onSlideChange,
  overlay,
  height,
}: HeroCarouselProps) {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const resumeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const slideCount = slides.length;

  const goToSlide = useCallback(
    (index: number) => {
      const next = ((index % slideCount) + slideCount) % slideCount;
      setCurrentSlide(next);
      onSlideChange?.(next);
    },
    [slideCount, onSlideChange],
  );

  const nextSlide = useCallback(() => goToSlide(currentSlide + 1), [currentSlide, goToSlide]);
  const prevSlide = useCallback(() => goToSlide(currentSlide - 1), [currentSlide, goToSlide]);

  const pauseAutoplay = useCallback(() => {
    setIsPaused(true);
    if (resumeTimeoutRef.current) clearTimeout(resumeTimeoutRef.current);
    resumeTimeoutRef.current = setTimeout(() => setIsPaused(false), interval * 2);
  }, [interval]);

  // Autoplay
  useEffect(() => {
    if (!autoplay || isPaused || slideCount <= 1) return;
    const timer = setInterval(nextSlide, interval);
    return () => clearInterval(timer);
  }, [autoplay, isPaused, interval, nextSlide, slideCount]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (resumeTimeoutRef.current) clearTimeout(resumeTimeoutRef.current);
    };
  }, []);

  if (slideCount === 0) return null;

  return (
    <section
      className={`relative ${height ?? 'h-[400px] md:h-[500px]'} overflow-hidden`}
      role="region"
      aria-roledescription="carousel"
      aria-label="Hero image carousel"
    >
      {/* Slides */}
      <div className="relative h-full w-full">
        {slides.map((slide, index) => (
          <div
            key={index}
            className={`absolute inset-0 transition-opacity duration-500 ${
              index === currentSlide ? 'opacity-100 z-10' : 'opacity-0 z-0'
            }`}
            role="group"
            aria-roledescription="slide"
            aria-label={`Slide ${index + 1} of ${slideCount}`}
            aria-hidden={index !== currentSlide}
          >
            <picture>
              {slide.mobileImage && (
                <source media="(max-width: 768px)" srcSet={slide.mobileImage} />
              )}
              <img
                src={slide.desktopImage}
                alt={slide.alt}
                className="absolute inset-0 w-full h-full object-cover"
                loading={index === 0 ? 'eager' : 'lazy'}
                decoding="async"
              />
            </picture>
            {/* Gradient overlay */}
            <div className={`absolute inset-0 bg-gradient-to-b ${overlay ? 'from-black/40 via-black/20 to-black/60' : 'from-transparent to-black/60'}`} />
            {/* Caption */}
            {slide.caption && (
              <div className="absolute bottom-16 left-0 right-0 z-20 px-6 text-white">
                <p className="text-lg md:text-xl font-medium max-w-xl">{slide.caption}</p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Overlay: logo, title, tagline */}
      {overlay && (overlay.logo || overlay.title || overlay.tagline) && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center pointer-events-none px-6 text-center">
          {overlay.logo && (
            <img
              src={overlay.logo}
              alt={overlay.logoAlt ?? ''}
              className="h-20 md:h-28 w-auto mb-4"
            />
          )}
          {overlay.title && (
            <h1 className="text-3xl md:text-5xl lg:text-6xl font-bold text-white tracking-wide drop-shadow-lg">
              {overlay.title}
            </h1>
          )}
          {overlay.tagline && (
            <p className="mt-2 text-lg md:text-2xl text-white/90 font-light italic drop-shadow-md">
              {overlay.tagline}
            </p>
          )}
          {overlay.ctaLabel && overlay.ctaHref && (
            <a
              href={overlay.ctaHref}
              className="pointer-events-auto mt-6 inline-block rounded-full bg-[color:var(--brand-primary)] px-8 py-3 text-white font-semibold hover:opacity-90 transition-opacity"
            >
              {overlay.ctaLabel}
            </a>
          )}
        </div>
      )}

      {/* Previous Arrow */}
      {slideCount > 1 && (
        <button
          type="button"
          onClick={() => {
            prevSlide();
            pauseAutoplay();
          }}
          className="absolute left-4 top-1/2 -translate-y-1/2 z-20 bg-white/20 backdrop-blur-sm p-2 rounded-full text-white hover:bg-white/30 transition-colors"
          aria-label="Previous slide"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      )}

      {/* Next Arrow */}
      {slideCount > 1 && (
        <button
          type="button"
          onClick={() => {
            nextSlide();
            pauseAutoplay();
          }}
          className="absolute right-4 top-1/2 -translate-y-1/2 z-20 bg-white/20 backdrop-blur-sm p-2 rounded-full text-white hover:bg-white/30 transition-colors"
          aria-label="Next slide"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}

      {/* Dot Indicators */}
      {slideCount > 1 && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex gap-2">
          {slides.map((_, index) => (
            <button
              key={index}
              type="button"
              onClick={() => {
                goToSlide(index);
                pauseAutoplay();
              }}
              className={`h-2 rounded-full transition-all ${
                currentSlide === index ? 'bg-white w-6' : 'bg-white/50 w-2'
              }`}
              aria-label={`Go to slide ${index + 1}`}
              aria-current={currentSlide === index ? 'true' : undefined}
            />
          ))}
        </div>
      )}

      {/* Scroll-down cue (only when single slide, since multi-slide has dot indicators) */}
      {slideCount === 1 && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 animate-bounce">
          <svg className="h-6 w-6 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      )}
    </section>
  );
}
