import type { HandlerDeps, AuthHandlerDeps, EmailSender } from '@botanarede/bonarjs-sdk-alpha/server'

/** Tables that accept anonymous writes (public form submissions). */
const PUBLIC_SUBMIT_TABLES = ['emails', 'reservas'] as const

/** Throw at startup if a required env var is missing. */
function requireEnv(name: string): string {
  const value = process.env[name]
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`)
  }
  return value
}

let _deps: HandlerDeps | null = null
let _authDeps: AuthHandlerDeps | null = null

/**
 * Console-based email sender for development.
 * Logs the code to stdout instead of sending a real email.
 */
const devEmailSender: EmailSender = {
  send: async (to, subject, htmlBody) => {
    console.log(`[DEV EMAIL] To: ${to} | Subject: ${subject}`)
    const codeMatch = htmlBody.match(/<h2[^>]*>(\d{6})<\/h2>/)
    if (codeMatch) {
      console.log(`[DEV EMAIL] Verification code: ${codeMatch[1]}`)
    }
  },
}

/**
 * Postmark email sender for production.
 */
function createPostmarkSender(serverToken: string): EmailSender {
  return {
    send: async (to, subject, htmlBody) => {
      const response = await fetch('https://api.postmarkapp.com/email', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Postmark-Server-Token': serverToken,
        },
        body: JSON.stringify({
          From: 'Login Botanarede <noreply@example.com>',
          To: to,
          Subject: subject,
          HtmlBody: htmlBody,
          MessageStream: 'outbound',
        }),
      })

      if (!response.ok) {
        const text = await response.text()
        throw new Error(`Postmark API failure: ${response.status} ${text}`)
      }
    },
  }
}

function getEmailSender(): EmailSender {
  const postmarkToken = process.env.POSTMARK_SERVER_TOKEN
  if (postmarkToken) {
    return createPostmarkSender(postmarkToken)
  }
  return devEmailSender
}

/**
 * Get base HandlerDeps for CRUD route handlers (singleton).
 */
export async function getHandlerDeps(): Promise<HandlerDeps> {
  if (_deps) return _deps

  const { createHandlerDeps } = await import('@botanarede/bonarjs-sdk-alpha/server')

  _deps = await createHandlerDeps({
    serviceAccountJson: process.env.FIREBASE_SERVICE_ACCOUNT_JSON,
    projectId: process.env.FIREBASE_PROJECT_ID ?? 'your-project-id',
    storageBucket: process.env.FIREBASE_STORAGE_BUCKET,
    publicSubmitTables: PUBLIC_SUBMIT_TABLES,
  })

  return _deps
}

/**
 * Get AuthHandlerDeps for auth route handlers (singleton).
 */
export async function getAuthHandlerDeps(): Promise<AuthHandlerDeps> {
  if (_authDeps) return _authDeps

  const { createAuthHandlerDeps } = await import('@botanarede/bonarjs-sdk-alpha/server')

  _authDeps = await createAuthHandlerDeps({
    serviceAccountJson: process.env.FIREBASE_SERVICE_ACCOUNT_JSON,
    projectId: process.env.FIREBASE_PROJECT_ID ?? 'your-project-id',
    storageBucket: process.env.FIREBASE_STORAGE_BUCKET,
    appId: requireEnv('FIREBASE_APP_ID'),
    emailSender: getEmailSender(),
    publicSubmitTables: PUBLIC_SUBMIT_TABLES,
  })

  return _authDeps
}
