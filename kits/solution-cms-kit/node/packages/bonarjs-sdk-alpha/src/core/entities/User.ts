import { z } from 'zod'

/**
 * Zod schema for a platform user.
 *
 * A user is the authenticated identity for an end consumer of a bonarjs app.
 * Only the email is strictly required; everything else is provider-supplied
 * and may or may not be present depending on the auth flow.
 */
export const UserSchema = z.object({
  id: z.string().optional(),
  name: z.string().optional(),
  email: z.string().email(),
})

export type User = z.infer<typeof UserSchema>
