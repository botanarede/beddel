import type { IMailAdapter } from '../../interfaces/IMailAdapter'
import type { MailPayload } from '../../types'

/** Dispatch a transactional email via the supplied mail adapter. */
export class SendMail {
  constructor(private readonly mail: IMailAdapter) {}

  async execute(payload: MailPayload): Promise<void> {
    return this.mail.send(payload)
  }
}
