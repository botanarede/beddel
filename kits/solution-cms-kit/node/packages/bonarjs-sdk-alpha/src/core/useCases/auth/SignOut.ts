import type { IAuthAdapter } from '../../interfaces/IAuthAdapter'

/** Signs the current user out. Idempotent when already signed out. */
export class SignOut {
  constructor(private readonly auth: IAuthAdapter) {}

  async execute(): Promise<void> {
    return this.auth.signOut()
  }
}
