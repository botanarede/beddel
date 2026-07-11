import type { IAuthAdapter } from '../../interfaces/IAuthAdapter'
import type { User } from '../../entities/User'

/** Returns the currently-signed-in user, or `null` when anonymous. */
export class GetCurrentUser {
  constructor(private readonly auth: IAuthAdapter) {}

  async execute(): Promise<User | null> {
    return this.auth.getCurrentUser()
  }
}
