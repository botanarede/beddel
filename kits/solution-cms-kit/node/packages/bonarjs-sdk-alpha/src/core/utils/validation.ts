import { ValidationError } from '../errors'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/**
 * Lightweight email-format check. Prefer Zod (`z.string().email()`) when you
 * already have a schema at hand; this helper is intended for throw-away
 * validation in adapter code.
 */
export function validateEmail(email: string): boolean {
  if (typeof email !== 'string') return false
  return EMAIL_RE.test(email)
}

/**
 * Assert that every listed field is present (non-`undefined`, non-`null`,
 * non-empty-string) on `obj`. Throws a {@link ValidationError} listing the
 * missing fields.
 */
export function validateRequired<T extends Record<string, unknown>>(
  obj: T,
  fields: readonly (keyof T)[],
): void {
  const missing: string[] = []
  for (const field of fields) {
    const value = obj[field]
    if (value === undefined || value === null || value === '') {
      missing.push(String(field))
    }
  }
  if (missing.length > 0) {
    throw new ValidationError(
      'validation/missing-fields',
      `Missing required field(s): ${missing.join(', ')}`,
    )
  }
}
