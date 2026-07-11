import { describe, expect, it } from 'vitest'

import { SignInEmailCode } from '../../../src/core/useCases/auth/SignInEmailCode'
import { SignInEmailPassword } from '../../../src/core/useCases/auth/SignInEmailPassword'
import { SignOut } from '../../../src/core/useCases/auth/SignOut'
import { LoginStatus } from '../../../src/core/types'
import { FakeAuth } from '../../fixtures/fakeAdapters'

describe('useCases/auth', () => {
  it('SignInEmailCode returns INVALID_EMAIL for a bad email', async () => {
    const auth = new FakeAuth()
    const result = await new SignInEmailCode(auth).execute('not-email', 1234)
    expect(result.message).toBe(LoginStatus.INVALID_EMAIL)
  })

  it('SignInEmailCode sends code then succeeds', async () => {
    const auth = new FakeAuth()
    const first = await new SignInEmailCode(auth).execute('a@b.com')
    expect(first.message).toBe(LoginStatus.EMAIL_SENT)
    const second = await new SignInEmailCode(auth).execute('a@b.com', 1234)
    expect(second.message).toBe(LoginStatus.SUCCESS)
  })

  it('SignInEmailPassword forwards to the adapter', async () => {
    const auth = new FakeAuth()
    const result = await new SignInEmailPassword(auth).execute('a@b.com', 'pw')
    expect(result.message).toBe(LoginStatus.SUCCESS)
  })

  it('SignOut clears the session', async () => {
    const auth = new FakeAuth()
    await new SignInEmailPassword(auth).execute('a@b.com', 'pw')
    await new SignOut(auth).execute()
    expect(auth.currentUser).toBeNull()
  })
})
