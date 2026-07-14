import { makeGetItems } from '@botanarede/bonarjs-sdk-alpha/server'
import { getHandlerDeps } from '@/lib/handler-deps'

let handler: ReturnType<typeof makeGetItems> | null = null

export async function POST(req: Request) {
  if (!handler) {
    const deps = await getHandlerDeps()
    handler = makeGetItems(deps)
  }
  return handler(req as any)
}
