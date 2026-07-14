import { NextResponse, type NextRequest } from 'next/server'

export interface CorsConfig {
  /** Comma-separated allowed origins, or "*" for wildcard (dev only). */
  allowedOrigins: string
}

const CORS_METHODS = 'GET,POST,PUT,DELETE,OPTIONS,PATCH'
const CORS_HEADERS =
  'Content-Type, Authorization, X-Firebase-AppCheck, X-Firebase-IdToken'

/**
 * Check if the request origin is in the allowed list.
 * Supports exact match and wildcard "*".
 */
function isAllowedOrigin(origin: string, allowed: Set<string>): boolean {
  if (allowed.has('*')) return true
  return allowed.has(origin)
}

/**
 * Factory for a Next.js CORS middleware function.
 *
 * Usage in `apps/api/src/middleware.ts`:
 * ```ts
 * import { createCorsMiddleware } from '@botanarede/bonarjs-sdk-alpha/server'
 * const corsMiddleware = createCorsMiddleware({ allowedOrigins: process.env.ALLOWED_ORIGINS ?? '' })
 * export function middleware(req) { return corsMiddleware(req) }
 * export const config = { matcher: ['/api/:path*'] }
 * ```
 */
export function createCorsMiddleware(corsConfig: CorsConfig) {
  const allowedSet = new Set(
    corsConfig.allowedOrigins
      .split(',')
      .map((o) => o.trim())
      .filter(Boolean),
  )

  return function middleware(request: NextRequest): NextResponse {
    const origin = request.headers.get('origin') ?? ''
    const originAllowed = isAllowedOrigin(origin, allowedSet)

    // Handle OPTIONS preflight
    if (request.method === 'OPTIONS') {
      if (!originAllowed) {
        return new NextResponse(null, { status: 403 })
      }
      return new NextResponse(null, {
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': origin,
          'Access-Control-Allow-Methods': CORS_METHODS,
          'Access-Control-Allow-Headers': CORS_HEADERS,
          'Access-Control-Allow-Credentials': 'true',
          'Access-Control-Max-Age': '86400',
        },
      })
    }

    // Non-preflight: add CORS headers if origin is allowed
    const response = NextResponse.next()

    if (originAllowed) {
      response.headers.set('Access-Control-Allow-Origin', origin)
      response.headers.set('Access-Control-Allow-Methods', CORS_METHODS)
      response.headers.set('Access-Control-Allow-Headers', CORS_HEADERS)
      response.headers.set('Access-Control-Allow-Credentials', 'true')
    }

    return response
  }
}
