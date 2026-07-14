import { makeEmailCodeAuth } from '@botanarede/bonarjs-sdk-alpha/server'
import { getAuthHandlerDeps } from '@/lib/handler-deps'

let handler: ReturnType<typeof makeEmailCodeAuth> | null = null

export async function POST(req: Request) {
  if (!handler) {
    const deps = await getAuthHandlerDeps()
    handler = makeEmailCodeAuth(deps)
  }
  return handler(req as any)
}
