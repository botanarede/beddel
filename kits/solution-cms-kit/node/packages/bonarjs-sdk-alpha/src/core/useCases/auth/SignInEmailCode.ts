import type { IAuthAdapter } from '../../interfaces/IAuthAdapter'
import { LoginStatus, type LoginResult } from '../../types'
import { AuthError } from '../../errors'
import { validateEmail } from '../../utils/validation'

/**
 * Two-phase email-code login.
 *
 * - Called without `code`: the adapter should send the code out-of-band and
 *   the use case returns `LoginStatus.EMAIL_SENT`.
 * - Called with `code`: the adapter should validate the code and complete
 *   sign-in; the use case returns `LoginStatus.SUCCESS` (with the user).
 */
export class SignInEmailCode {
  constructor(private readonly auth: IAuthAdapter) {}

  async execute(email: string, code?: number): Promise<LoginResult> {
    if (!validateEmail(email)) {
      return { message: LoginStatus.INVALID_EMAIL }
    }
    try {
      return await this.auth.signInWithEmailCode(email, code)
    } catch (err) {
      if (err instanceof AuthError) throw err
      return { message: LoginStatus.ERROR }
    }
  }
}
