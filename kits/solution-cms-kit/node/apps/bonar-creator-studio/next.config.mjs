import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))

function resolveDistDir() {
  const tenantId = process.env.EXPORT_TENANT_ID
  if (!tenantId) return undefined

  // Kit-internal path: node/apps/bonar-creator-studio → node/tenants/{id}.json
  const tenantPath = resolve(__dirname, '..', '..', 'tenants', `${tenantId}.json`)
  try {
    const raw = readFileSync(tenantPath, 'utf-8')
    const data = JSON.parse(raw)
    const id = data?.metadata?.id ?? tenantId
    const exportDomain = data?.metadata?.exportDomain
    const distPath = `${exportDomain ?? id}.${process.env.PLATFORM_DOMAIN ?? 'example.com'}`
    console.log(`[next.config] Export mode: tenant="${id}", distDir=sites/${distPath}/`)
    // Kit-internal path: node/apps/bonar-creator-studio → node/sites/{domain}
    return `../../sites/${distPath}`
  } catch (err) {
    throw new Error(
      `[next.config] EXPORT_TENANT_ID="${tenantId}" but tenants/${tenantId}.json not found.\n` +
        `Error: ${err instanceof Error ? err.message : String(err)}`,
    )
  }
}

const distDir = resolveDistDir()

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  poweredByHeader: false,
  reactStrictMode: true,
  ...(distDir ? { distDir } : {}),
  images: {
    unoptimized: true,
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'firebasestorage.googleapis.com',
      },
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
      },
    ],
    formats: ['image/avif', 'image/webp'],
  },
  transpilePackages: ['@botanarede/bonarjs-sdk-alpha', '@botanarede/core', '@botanarede/ui-react'],
}

export default nextConfig
