import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { HttpAuthAdapter } from '../../../src/adapters/HttpAuthAdapter'
import { LoginStatus } from '../../../src/core/types'

const API = 'https://api.example.com'

let lastBody: Record<string, unknown> | undefined

const server = setupServer(
  http.post(`${API}/api/auth`, async ({ request }) => {
    lastBody = (await request.json()) as Record<string, unknown>
    if (lastBody.code === 1234) {
      return HttpResponse.json({ token: 'custom-token' }, { status: 200 })
    }
    if (lastBody.code !== undefined) {
      return HttpResponse.json({}, { status: 200 })
    }
    return HttpResponse.json({ message: 'Code sent.' }, { status: 200 })
  }),
  http.post(`${API}/api/auth/checkUserInDatabase`, () =>
    HttpResponse.json(true, { status: 200 }),
  ),
  http.post(`${API}/api/auth/verifyAppCheck`, () =>
    HttpResponse.json({ token: 'ac-token' }, { status: 200 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('integration/HttpAuthAdapter', () => {
  it('issues the code when called without code', async () => {
    const adapter = new HttpAuthAdapter({ apiUrl: API, apiKey: 'c' })
    const result = await adapter.signInWithEmailCode('a@b.com')
    expect(result.message).toBe(LoginStatus.EMAIL_SENT)
    expect(lastBody).toEqual({ email: 'a@b.com' })
  })

  it('completes sign-in with a valid code', async () => {
    const adapter = new HttpAuthAdapter({ apiUrl: API, apiKey: 'c' })
    const result = await adapter.signInWithEmailCode('a@b.com', 1234)
    expect(result.message).toBe(LoginStatus.SUCCESS)
    expect(result.user?.email).toBe('a@b.com')
  })

  it('returns INVALID_CODE when the server omits a token', async () => {
    const adapter = new HttpAuthAdapter({ apiUrl: API, apiKey: 'c' })
    const result = await adapter.signInWithEmailCode('a@b.com', 9999)
    expect(result.message).toBe(LoginStatus.INVALID_CODE)
  })

  it('exchangeEmailCodeForToken returns the token string', async () => {
    const adapter = new HttpAuthAdapter({ apiUrl: API, apiKey: 'c' })
    expect(await adapter.exchangeEmailCodeForToken('a@b.com', 1234)).toBe('custom-token')
  })

  it('checkUserInDatabase returns boolean', async () => {
    const adapter = new HttpAuthAdapter({ apiUrl: API, apiKey: 'c' })
    expect(await adapter.checkUserInDatabase('a@b.com')).toBe(true)
  })

  it('fetchAppCheckToken returns a token envelope', async () => {
    const adapter = new HttpAuthAdapter({ apiUrl: API, apiKey: 'c' })
    const env = await adapter.fetchAppCheckToken()
    expect(env?.token).toBe('ac-token')
    expect(env?.expireTimeMillis).toBeGreaterThan(Date.now())
  })
})
