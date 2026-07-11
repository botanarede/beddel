import { makeDeleteItemById } from '@botanarede/bonarjs-sdk-alpha/server'
import { getHandlerDeps } from '@/lib/handler-deps'

let handler: ReturnType<typeof makeDeleteItemById> | null = null

export async function POST(req: Request) {
  if (!handler) {
    const deps = await getHandlerDeps()
    handler = makeDeleteItemById(deps)
  }
  return handler(req as any)
}
