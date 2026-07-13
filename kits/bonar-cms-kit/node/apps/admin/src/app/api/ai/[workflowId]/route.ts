import { NextResponse, type NextRequest } from 'next/server'
import { validateCustomer, invalidCustomerResponse } from '@botanarede/bonarjs-sdk-alpha/server'
import { getHandlerDeps } from '@/lib/handler-deps'

/**
 * AI Proxy Route — POST /api/ai/[workflowId]
 *
 * Authenticates the request via customer token, then proxies to the
 * Beddel FastAPI internal service (Tier 3) and streams the SSE response
 * back to the client without buffering.
 *
 * Auth: Authorization header containing customer document ID
 * Body: JSON payload forwarded as-is to Tier 3
 * Response: SSE stream (text/event-stream)
 */
export async function POST(
  req: NextRequest,
  { params }: { params: { workflowId: string } },
) {
  // --- 1. Validate customer auth ---
  const deps = await getHandlerDeps()
  const customer = await validateCustomer(req, deps.db)
  if (!customer) return invalidCustomerResponse()

  // --- 2. Resolve Tier 3 URL ---
  const baseUrl = process.env.BEDDEL_FASTAPI_INTERNAL_URL
  if (!baseUrl) {
    console.error('[api/ai] BEDDEL_FASTAPI_INTERNAL_URL is not configured')
    return NextResponse.json(
      { error: 'AI service not configured.' },
      { status: 503 },
    )
  }

  const { workflowId } = params
  const targetUrl = `${baseUrl.replace(/\/$/, '')}/api/${workflowId}`

  // --- 3. Forward request body to Tier 3 ---
  let body: string
  try {
    body = await req.text()
  } catch {
    body = '{}'
  }

  let upstreamResponse: Response
  try {
    upstreamResponse = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body,
    })
  } catch (err) {
    console.error('[api/ai] Failed to reach Tier 3:', err)
    return NextResponse.json(
      { error: 'AI service unavailable.' },
      { status: 502 },
    )
  }

  // --- 4. Forward non-2xx errors ---
  if (!upstreamResponse.ok) {
    const errorBody = await upstreamResponse.text().catch(() => 'Unknown error')
    return new NextResponse(errorBody, {
      status: upstreamResponse.status,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  // --- 5. Stream SSE response back to client ---
  if (!upstreamResponse.body) {
    return NextResponse.json(
      { error: 'No response body from AI service.' },
      { status: 502 },
    )
  }

  return new NextResponse(upstreamResponse.body as ReadableStream, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  })
}
