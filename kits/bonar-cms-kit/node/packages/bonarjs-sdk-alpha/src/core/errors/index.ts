/**
 * Base error class for every error thrown by `@botanarede/bonarjs-sdk-alpha`.
 *
 * All specialised errors extend this class so consumers can discriminate
 * with a single `instanceof BonarJsError` check and still access the
 * original cause.
 */
export class BonarJsError extends Error {
  public readonly code: string
  public readonly cause?: unknown
  public readonly status?: number

  constructor(
    code: string,
    message: string,
    options?: { cause?: unknown; status?: number },
  ) {
    super(message)
    this.name = 'BonarJsError'
    this.code = code
    this.cause = options?.cause
    this.status = options?.status
  }
}

/** Thrown for auth adapter / flow failures. */
export class AuthError extends BonarJsError {
  constructor(
    code: string,
    message: string,
    options?: { cause?: unknown; status?: number },
  ) {
    super(code, message, options)
    this.name = 'AuthError'
  }
}

/** Thrown for database adapter / CRUD failures (including HTTP non-2xx). */
export class DatabaseError extends BonarJsError {
  constructor(
    code: string,
    message: string,
    options?: { cause?: unknown; status?: number },
  ) {
    super(code, message, options)
    this.name = 'DatabaseError'
  }
}

/** Thrown when the cache adapter cannot read or write. */
export class CacheError extends BonarJsError {
  constructor(
    code: string,
    message: string,
    options?: { cause?: unknown; status?: number },
  ) {
    super(code, message, options)
    this.name = 'CacheError'
  }
}

/** Thrown for programmer / schema validation errors. */
export class ValidationError extends BonarJsError {
  constructor(
    code: string,
    message: string,
    options?: { cause?: unknown; status?: number },
  ) {
    super(code, message, options)
    this.name = 'ValidationError'
  }
}

/** Thrown by mail adapter failures. */
export class MailError extends BonarJsError {
  constructor(
    code: string,
    message: string,
    options?: { cause?: unknown; status?: number },
  ) {
    super(code, message, options)
    this.name = 'MailError'
  }
}
