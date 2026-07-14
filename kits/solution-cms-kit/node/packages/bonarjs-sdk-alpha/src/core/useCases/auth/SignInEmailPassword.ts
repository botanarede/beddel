import type { IAuthAdapter } from '../../interfaces/IAuthAdapter'
import { LoginStatus, type LoginResult } from '../../types'
import { AuthError } from '../../errors'

/** Signs a user in with email + password via the supplied auth adapter. */
export class SignInEmailPassword {
  constructor(private readonly auth: IAuthAdapter) {}

  /**
   * @param email — user email.
   * @param password — user password.
   * @returns A {@link LoginResult} describing the outcome.
   * @throws AuthError when the adapter throws an unexpected error.
   */
  async execute(email: string, password: string): Promise<LoginResult> {
    try {
      return await this.auth.signInWithEmailPassword(email, password)
    } catch (err) {
      if (err instanceof AuthError) throw err
      return { message: LoginStatus.ERROR }
    }
  }
}
