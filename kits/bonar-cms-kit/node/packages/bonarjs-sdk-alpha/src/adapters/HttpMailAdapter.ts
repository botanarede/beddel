import type { IMailAdapter } from '../core/interfaces/IMailAdapter'
import type { ITokenProvider } from '../core/interfaces/ITokenProvider'
import type { MailPayload } from '../core/types'
import { MailError } from '../core/errors'

/** Configuration for {@link HttpMailAdapter}. */
export interface HttpMailAdapterConfig {
  apiUrl: string
  apiKey: string
  tokenProvider?: ITokenProvider
  /** Defaults to `/api/mail/dispatchEventTicket`. */
  endpoint?: string
  fetchImpl?: typeof fetch
}

const DEFAULT_ENDPOINT = '/api/mail/dispatchEventTicket'

/** HTTP adapter for the mail endpoint exposed by `bonar-cms-api`. */
export class HttpMailAdapter implements IMailAdapter {
  private readonly apiUrl: string
  private readonly apiKey: string
  private readonly tokenProvider?: ITokenProvider
  private readonly endpoint: string
  private readonly fetchImpl: typeof fetch

  constructor(config: HttpMailAdapterConfig) {
    if (!config.apiUrl) {
      throw new MailError(
        'mail/invalid-config',
        'HttpMailAdapter requires a non-empty apiUrl.',
      )
    }
    this.apiUrl = config.apiUrl.replace(/\/+$/, '')
    this.apiKey = config.apiKey
    this.tokenProvider = config.tokenProvider
    this.endpoint = config.endpoint ?? DEFAULT_ENDPOINT
    this.fetchImpl = config.fetchImpl ?? globalThis.fetch.bind(globalThis)
  }

  private async buildHeaders(): Promise<Record<string, string>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Authorization: this.apiKey,
    }
    if (this.tokenProvider) {
      try {
        const appCheck = await this.tokenProvider.getAppCheckToken()
        if (appCheck) headers['X-Firebase-AppCheck'] = appCheck
      } catch {
        /* ignore */
      }
      try {
        const idToken = await this.tokenProvider.getIdToken()
        if (idToken) headers['X-Firebase-IdToken'] = idToken
      } catch {
        /* ignore */
      }
    }
    return headers
  }

  async send(payload: MailPayload): Promise<void> {
    const headers = await this.buildHeaders()
    let response: Response
    try {
      response = await this.fetchImpl(`${this.apiUrl}${this.endpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        mode: 'cors',
      })
    } catch (err) {
      throw new MailError(
        'mail/network-error',
        `Network error while sending mail to ${this.endpoint}`,
        { cause: err },
      )
    }
    if (!response.ok) {
      throw new MailError(
        'mail/http-error',
        `Mail API request failed: ${response.status} ${response.statusText}`,
        { status: response.status },
      )
    }
  }
}
