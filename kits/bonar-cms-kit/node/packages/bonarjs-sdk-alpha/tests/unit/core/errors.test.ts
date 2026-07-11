import { describe, expect, it } from 'vitest'

import {
  AuthError,
  BonarJsError,
  CacheError,
  DatabaseError,
  MailError,
  ValidationError,
} from '../../../src/core/errors'

describe('core/errors', () => {
  it('every subclass extends BonarJsError', () => {
    expect(new AuthError('a/x', 'msg')).toBeInstanceOf(BonarJsError)
    expect(new DatabaseError('d/x', 'msg')).toBeInstanceOf(BonarJsError)
    expect(new CacheError('c/x', 'msg')).toBeInstanceOf(BonarJsError)
    expect(new ValidationError('v/x', 'msg')).toBeInstanceOf(BonarJsError)
    expect(new MailError('m/x', 'msg')).toBeInstanceOf(BonarJsError)
  })

  it('carries code, status, and cause', () => {
    const cause = new Error('root')
    const err = new DatabaseError('database/http-error', 'bad', {
      status: 500,
      cause,
    })
    expect(err.code).toBe('database/http-error')
    expect(err.status).toBe(500)
    expect(err.cause).toBe(cause)
    expect(err.name).toBe('DatabaseError')
  })
})
