'use client'

import { useEffect, useRef } from 'react'
import Image from 'next/image'
import type { RadarArticle, RadarProduct } from '@/types/radar'
import { trackProductClick, trackProductVisible } from '@/lib/radar-tracking'

interface ProductEmbedProps {
  product: RadarProduct
  article?: RadarArticle
}

export function ProductEmbed({ product, article }: ProductEmbedProps) {
  const linkRef = useRef<HTMLAnchorElement>(null)
  const hasFiredVisible = useRef(false)

  // IntersectionObserver — fire trackProductVisible once when 50% visible
  useEffect(() => {
    if (!article) return
    const el = linkRef.current
    if (!el) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasFiredVisible.current) {
          hasFiredVisible.current = true
          trackProductVisible(article, product)
          observer.disconnect()
        }
      },
      { threshold: 0.5 },
    )

    observer.observe(el)
    return () => observer.disconnect()
  }, [article, product])

  const handleClick = () => {
    if (article) {
      trackProductClick(article, product)
    }
  }

  const discountPct = Math.round(
    ((product.pricing.originalPrice - product.pricing.price) / product.pricing.originalPrice) * 100,
  )

  return (
    <a
      ref={linkRef}
      href={product.links.salesPage}
      target="_blank"
      rel="noopener noreferrer"
      onClick={handleClick}
      className="group mt-4 block overflow-hidden rounded-2xl border border-[#95d5b2]/30 bg-gradient-to-br from-[hsl(147,20%,97%)] to-[hsl(147,25%,94%)] transition-all duration-300 hover:border-[#95d5b2]/60 hover:shadow-[0_4px_24px_rgba(149,213,178,0.2)]"
    >
      {/* Product image */}
      <div className="relative aspect-[16/9] overflow-hidden bg-[#e8f5ee]">
        <Image
          src={product.image.url}
          alt={product.image.alt}
          fill
          className="object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          sizes="(max-width: 768px) 100vw, 640px"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent" />

        {/* Badge overlay */}
        <div className="absolute left-3 top-3">
          <span className="inline-flex items-center gap-1 rounded-full bg-[#2d6a4f]/90 px-2.5 py-1 text-[10px] font-semibold tracking-wider text-white backdrop-blur-sm">
            <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor" className="opacity-80">
              <path d="M8 0l2.5 5.3L16 6.2l-4 3.8 1 5.5L8 12.8l-5 2.7 1-5.5-4-3.8 5.5-.9z" />
            </svg>
            {product.badge}
          </span>
        </div>

        {/* Discount badge */}
        {discountPct > 0 && (
          <div className="absolute right-3 top-3">
            <span className="rounded-full bg-red-500/90 px-2 py-0.5 text-[10px] font-bold text-white backdrop-blur-sm">
              -{discountPct}%
            </span>
          </div>
        )}

        {/* Price overlay at bottom */}
        <div className="absolute bottom-0 left-0 right-0 flex items-end justify-between px-4 pb-3">
          <div>
            <p className="text-xs font-medium text-white/80 drop-shadow-sm">
              {product.vertical}
            </p>
          </div>
          <div className="flex items-baseline gap-2">
            {discountPct > 0 && (
              <span className="text-xs text-white/50 line-through drop-shadow-sm">
                R$ {product.pricing.originalPrice.toFixed(0)}
              </span>
            )}
            <span className="text-xl font-bold text-white drop-shadow-md">
              R$ {product.pricing.price.toFixed(0)}
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 md:p-5">
        <h4 className="font-sans text-base font-semibold leading-snug text-[#1b4332] group-hover:text-[#2d6a4f]">
          {product.title}
        </h4>
        <p className="mt-1.5 font-sans text-sm leading-relaxed text-[#1b4332]/60">
          {product.shortDescription}
        </p>
        <p className="mt-1.5 text-[11px] text-[#1b4332]/40">
          por {product.creator.name} · {product.creator.credential}
        </p>

        {/* CTA */}
        <div className="mt-3 flex items-center justify-between border-t border-[#95d5b2]/20 pt-3">
          <span className="text-[10px] text-[#1b4332]/40">
            {product.pricing.installments} · Garantia {product.guarantee}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#2d6a4f] px-4 py-1.5 text-xs font-medium text-white transition-all duration-200 group-hover:bg-[#1b4332] group-hover:shadow-md">
            Conhecer curso
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </span>
        </div>
      </div>
    </a>
  )
}
