import type { IAuthAdapter } from '../../interfaces/IAuthAdapter'
import type { OAuthProvider, OAuthSignInOptions, LoginResult } from '../../types'
import { LoginStatus } from '../../types'
import { AuthError } from '../../errors'

/** Initiates an OAuth sign-in flow via the supplied auth adapter. */
export class SignInOAuth {
  constructor(private readonly auth: IAuthAdapter) {}

  async execute(
    provider: OAuthProvider,
    options?: OAuthSignInOptions,
  ): Promise<LoginResult> {
    try {
      return await this.auth.signInWithOAuth(provider, options)
    } catch (err) {
      if (err instanceof AuthError) throw err
      return { message: LoginStatus.ERROR }
    }
  }
}
