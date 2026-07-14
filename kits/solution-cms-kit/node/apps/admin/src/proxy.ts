import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import {
  authMiddleware,
  redirectToLogin,
  redirectToHome,
} from 'next-firebase-auth-edge'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Firebase service account credentials for next-firebase-auth-edge.
 */
export interface ServiceAccountCredentials {
  projectId: string
  clientEmail: string
  privateKey: string
}

// ---------------------------------------------------------------------------
// Module-level flags (avoid repeated console warnings)
// ---------------------------------------------------------------------------

let serviceAccountWarningLogged = false
let serviceAccountParseErrorLogged = false

// ---------------------------------------------------------------------------
// Tenant Resolution
// ---------------------------------------------------------------------------

/**
 * Resolve tenant ID from the request hostname.
 *
 * Uses the Vercel Platforms pattern: read `host` header, strip port, match patterns.
 *
 * | Hostname                        | Resolved Tenant |
 * |---------------------------------|-----------------|
 * | localhost                        | null            |
 * | 127.0.0.1                       | null            |
 * | cms-admin.local                  | null (dev)      |
 * | admin.platform.example.com       | null (selector) |
 * | admin.tenant-a.example.com       | tenant-a        |
 * | tenant-a.platform.example.com    | tenant-a        |
 * | www.platform.example.com         | null (reserved) |
 * | api.platform.example.com         | null (reserved) |
 *
 * If `KNOWN_TENANTS` env var is set (comma-separated), only IDs in that
 * allow-list are returned. If unset, any resolved tenant is accepted
 * (backward compat for local dev).
 */
function resolveTenant(request: NextRequest): string | null {
  const rawHost = request.headers.get('host') ?? ''

  // Edge cases: empty host, IPv6 brackets
  if (!rawHost || rawHost.startsWith('[')) return null

  // Strip port and trailing dots
  const host = rawHost.split(':')[0].replace(/\.+$/, '')

  if (!host) return null

  // Configurable platform domain and local hostname
  const platformDomain = process.env.PLATFORM_DOMAIN ?? 'example.com'
  const adminLocalHostname = process.env.ADMIN_LOCAL_HOSTNAME ?? 'cms-admin.local'
  const adminPlatformDomain = process.env.ADMIN_PLATFORM_DOMAIN ?? `admin.${platformDomain}`

  // Local dev hostnames → null (show selector)
  if (host === 'localhost' || host === '127.0.0.1') return null
  if (host === adminLocalHostname) return null

  // Generic admin domain → null (show selector)
  if (host === adminPlatformDomain) return null

  let tenantId: string | null = null

  // Pattern: admin.{tenant}.{tld} → tenant
  const platformParts = platformDomain.split('.')
  const platformRegex = new RegExp(
    `^admin\\.([a-z0-9-]+)\\.${platformParts.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\.')}$`,
  )
  const adminMatch = host.match(platformRegex)
  if (adminMatch) {
    tenantId = adminMatch[1]
  }

  // Pattern: {tenant}.{platformDomain} (subdomain not in reserved list)
  if (!tenantId && host.endsWith('.' + platformDomain)) {
    const parts = host.split('.')
    const subdomain = parts[0]
    if (['admin', 'www', 'api'].includes(subdomain)) return null
    tenantId = subdomain
  }

  if (!tenantId) return null

  // Allow-list enforcement
  const knownTenantsRaw = process.env.KNOWN_TENANTS
  if (knownTenantsRaw) {
    const knownTenants = new Set(
      knownTenantsRaw
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
    )
    if (!knownTenants.has(tenantId)) return null
  }

  return tenantId
}

// ---------------------------------------------------------------------------
// CORS
// ---------------------------------------------------------------------------

const CORS_METHODS = 'GET,POST,PUT,DELETE,OPTIONS,PATCH'
const CORS_HEADERS =
  'Content-Type, Authorization, X-Firebase-AppCheck, X-Firebase-IdToken'

function getAllowedOrigins(): Set<string> {
  const raw = process.env.ALLOWED_ORIGINS ?? 'http://localhost:3000'
  return new Set(
    raw
      .split(',')
      .map((o) => o.trim())
      .filter(Boolean),
  )
}

/**
 * Handle CORS for API requests.
 *
 * - OPTIONS → 204 with CORS headers (or 403 if origin not allowed)
 * - Non-OPTIONS → NextResponse.next() with CORS headers attached
 */
function handleCors(request: NextRequest): NextResponse {
  const origin = request.headers.get('origin') ?? ''
  const allowed = getAllowedOrigins()
  const originAllowed = allowed.has('*') || allowed.has(origin)

  if (request.method === 'OPTIONS') {
    if (!originAllowed) return new NextResponse(null, { status: 403 })
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

  const response = NextResponse.next()
  if (originAllowed && origin) {
    response.headers.set('Access-Control-Allow-Origin', origin)
    response.headers.set('Access-Control-Allow-Methods', CORS_METHODS)
    response.headers.set('Access-Control-Allow-Headers', CORS_HEADERS)
    response.headers.set('Access-Control-Allow-Credentials', 'true')
  }
  return response
}

/**
 * Attach CORS headers to an existing response based on the request origin.
 */
function withCorsHeaders(response: NextResponse, request: NextRequest): NextResponse {
  const origin = request.headers.get('origin') ?? ''
  const allowed = getAllowedOrigins()
  const originAllowed = allowed.has('*') || allowed.has(origin)

  if (originAllowed && origin) {
    response.headers.set('Access-Control-Allow-Origin', origin)
    response.headers.set('Access-Control-Allow-Methods', CORS_METHODS)
    response.headers.set('Access-Control-Allow-Headers', CORS_HEADERS)
    response.headers.set('Access-Control-Allow-Credentials', 'true')
  }

  return response
}

// ---------------------------------------------------------------------------
// Service Account
// ---------------------------------------------------------------------------

/**
 * Read Firebase service account credentials from environment.
 *
 * - If `FIREBASE_SERVICE_ACCOUNT_JSON` is missing/empty: returns `undefined`
 *   (next-firebase-auth-edge handles emulator mode automatically).
 * - If present but invalid JSON: logs error once, returns `undefined`.
 * - If `NODE_ENV=production` and missing: logs a one-time warning.
 */
function getServiceAccount(): ServiceAccountCredentials | undefined {
  const json = process.env.FIREBASE_SERVICE_ACCOUNT_JSON

  if (!json || json.trim() === '') {
    if (process.env.NODE_ENV === 'production' && !serviceAccountWarningLogged) {
      serviceAccountWarningLogged = true
      console.warn(
        '[proxy] FIREBASE_SERVICE_ACCOUNT_JSON is not set in production. ' +
          'Auth token refresh will not work.',
      )
    }
    return undefined
  }

  try {
    const parsed = JSON.parse(json) as Record<string, unknown>
    return {
      projectId: parsed.project_id as string,
      clientEmail: parsed.client_email as string,
      privateKey: parsed.private_key as string,
    }
  } catch {
    if (!serviceAccountParseErrorLogged) {
      serviceAccountParseErrorLogged = true
      console.error(
        '[proxy] Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON. ' +
          'Falling back to emulator mode.',
      )
    }
    return undefined
  }
}

// ---------------------------------------------------------------------------
// Main Proxy Function
// ---------------------------------------------------------------------------

/**
 * Proxy function for Next.js middleware.
 *
 * Responsibilities:
 * 1. Tenant resolution from hostname → x-tenant-id header
 * 2. CORS for /api/* (external tenant frontends)
 * 3. Server-side auth via next-firebase-auth-edge session cookies
 */
export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl

  // --- Static assets: pass through ---
  if (pathname.startsWith('/_next') || pathname.startsWith('/favicon')) {
    return NextResponse.next()
  }

  // --- Tenant resolution (runs for every request) ---
  const tenantId = resolveTenant(request)

  // --- OPTIONS preflight on /api/*: CORS-only response (no auth) ---
  if (request.method === 'OPTIONS' && pathname.startsWith('/api/')) {
    const corsResponse = handleCors(request)
    if (tenantId) {
      corsResponse.headers.set('x-tenant-id', tenantId)
    }
    return corsResponse
  }

  // --- All other routes: auth middleware ---
  return authMiddleware(request, {
    loginPath: '/api/login',
    logoutPath: '/api/logout',
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY!,
    cookieName: '__session',
    cookieSignatureKeys: [
      process.env.AUTH_COOKIE_SECRET ??
        'CHANGE-ME-insecure-dev-only-cookie-secret',
    ],
    cookieSerializeOptions: {
      path: '/',
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax' as const,
      maxAge: 24 * 60 * 60, // 24 hours
    },
    serviceAccount: getServiceAccount(),
    enableMultipleCookies: true,

    handleValidToken: async ({ decodedToken }, headers) => {
      // Inject tenant and user context into request headers
      if (tenantId) {
        headers.set('x-tenant-id', tenantId)
      }
      headers.set('x-user-uid', decodedToken.uid)
      headers.set('x-user-email', decodedToken.email ?? '')

      // Authenticated user should not see /login → redirect to home
      if (pathname === '/login') {
        return redirectToHome(request)
      }

      // API routes: pass through with CORS headers
      if (pathname.startsWith('/api/')) {
        const response = NextResponse.next({ request: { headers } })
        return withCorsHeaders(response, request)
      }

      return NextResponse.next({ request: { headers } })
    },

    handleInvalidToken: async (_reason) => {
      // API routes: pass through (route handler returns 401)
      if (pathname.startsWith('/api/')) {
        const response = NextResponse.next()
        if (tenantId) {
          response.headers.set('x-tenant-id', tenantId)
        }
        return withCorsHeaders(response, request)
      }

      return redirectToLogin(request, {
        path: '/login',
        publicPaths: ['/login'],
      })
    },

    handleError: async (error) => {
      console.error('[proxy] Auth error:', error)

      // Same logic as handleInvalidToken
      if (pathname.startsWith('/api/')) {
        const response = NextResponse.next()
        if (tenantId) {
          response.headers.set('x-tenant-id', tenantId)
        }
        return withCorsHeaders(response, request)
      }

      return redirectToLogin(request, {
        path: '/login',
        publicPaths: ['/login'],
      })
    },
  })
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export const config = {
  matcher: [
    '/api/:path*',
    '/',
    '/((?!_next|favicon.ico|.*\\.).*)',
  ],
}
