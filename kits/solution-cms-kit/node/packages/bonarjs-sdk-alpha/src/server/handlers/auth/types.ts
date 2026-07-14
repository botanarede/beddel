import type { HandlerDeps } from '../types'

/**
 * Narrow contract for Firebase Admin Auth operations needed by auth handlers.
 * Consumers wire the real `firebase-admin/auth` methods into this interface.
 */
export interface AdminAuth {
  createUser(properties: {
    email: string
    emailVerified?: boolean
  }): Promise<{ uid: string }>
  createCustomToken(
    uid: string,
    claims?: Record<string, unknown>,
  ): Promise<string>
  getUserByEmail(
    email: string,
  ): Promise<{ uid: string; email?: string } | null>
  updateUser(
    uid: string,
    properties: { emailVerified?: boolean },
  ): Promise<void>
}

/**
 * Contract for App Check token issuance (server-side).
 * Separate from AppCheckVerifier (read-only verification).
 */
export interface AppCheckIssuer {
  createToken(
    appId: string,
    options?: { ttlMillis?: number },
  ): Promise<{ token: string; ttlMillis: number }>
}

/**
 * Abstract email sender — SDK stays infrastructure-agnostic.
 * Consumers inject Postmark, SendGrid, or a dev console.log stub.
 */
export interface EmailSender {
  send(to: string, subject: string, htmlBody: string): Promise<void>
}

/**
 * Extended dependencies for auth route handlers.
 * Adds issuance capabilities (create users, mint tokens, send emails)
 * on top of the base CRUD verification capabilities.
 */
export interface AuthHandlerDeps extends HandlerDeps {
  adminAuth: AdminAuth
  appCheckIssuer: AppCheckIssuer
  emailSender: EmailSender
  /** Firebase App ID for App Check token creation. */
  appId: string
}
