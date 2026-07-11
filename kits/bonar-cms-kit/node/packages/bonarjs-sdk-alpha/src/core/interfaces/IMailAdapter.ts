import type { MailPayload } from '../types'

/** Transactional mail capability. */
export interface IMailAdapter {
  /** Send a transactional email described by `payload`. */
  send(payload: MailPayload): Promise<void>
}
