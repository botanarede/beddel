import { makeSetItem } from '@botanarede/bonarjs-sdk-alpha/server'
import { getHandlerDeps } from '@/lib/handler-deps'

let handler: ReturnType<typeof makeSetItem> | null = null

export async function POST(req: Request) {
  if (!handler) {
    const deps = await getHandlerDeps()
    handler = makeSetItem(deps)
  }
  return handler(req as any)
}
