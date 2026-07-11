import { describe, expect, it } from 'vitest'

import { validateEmail, validateRequired } from '../../../src/core/utils/validation'
import { ValidationError } from '../../../src/core/errors'

describe('core/utils/validation', () => {
  describe('validateEmail', () => {
    it('accepts well-formed emails', () => {
      expect(validateEmail('a@b.com')).toBe(true)
      expect(validateEmail('ada.lovelace@example.co.uk')).toBe(true)
    })
    it('rejects malformed emails', () => {
      expect(validateEmail('not-email')).toBe(false)
      expect(validateEmail('a@b')).toBe(false)
      expect(validateEmail('')).toBe(false)
    })
    it('rejects non-strings defensively', () => {
      // @ts-expect-error — deliberate bad input
      expect(validateEmail(123)).toBe(false)
    })
  })

  describe('validateRequired', () => {
    it('passes when all fields are present', () => {
      expect(() =>
        validateRequired({ a: 1, b: 'x' }, ['a', 'b']),
      ).not.toThrow()
    })
    it('throws listing missing fields', () => {
      try {
        validateRequired({ a: 1, b: '' } as Record<string, unknown>, ['a', 'b'])
      } catch (err) {
        expect(err).toBeInstanceOf(ValidationError)
        expect((err as ValidationError).message).toContain('b')
        return
      }
      throw new Error('expected to throw')
    })
  })
})
