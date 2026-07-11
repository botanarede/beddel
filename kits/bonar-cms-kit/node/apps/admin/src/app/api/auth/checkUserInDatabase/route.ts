import { makeCheckUserInDatabase } from '@botanarede/bonarjs-sdk-alpha/server'
import { getAuthHandlerDeps } from '@/lib/handler-deps'

let handler: ReturnType<typeof makeCheckUserInDatabase> | null = null

export async function POST(req: Request) {
  if (!handler) {
    const deps = await getAuthHandlerDeps()
    handler = makeCheckUserInDatabase(deps)
  }
  return handler(req as any)
}
