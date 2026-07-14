import { describe, expect, it } from 'vitest'

import {
  DynamicTableSchema,
  EventSchema,
  UserSchema,
  validateAndConvertEvent,
} from '../../../src/core/entities'

describe('core/entities', () => {
  describe('UserSchema', () => {
    it('accepts a minimal user (email only)', () => {
      expect(UserSchema.parse({ email: 'a@b.com' })).toEqual({ email: 'a@b.com' })
    })

    it('accepts optional name and id', () => {
      const parsed = UserSchema.parse({
        id: 'u1',
        name: 'Ada',
        email: 'ada@example.com',
      })
      expect(parsed.name).toBe('Ada')
    })

    it('rejects malformed email', () => {
      expect(() => UserSchema.parse({ email: 'not-an-email' })).toThrow()
    })

    it('rejects missing email', () => {
      expect(() => UserSchema.parse({})).toThrow()
    })
  })

  describe('DynamicTableSchema', () => {
    it('accepts all-optional shape', () => {
      expect(DynamicTableSchema.parse({})).toEqual({})
    })

    it('accepts items as any array', () => {
      const parsed = DynamicTableSchema.parse({ items: [{ a: 1 }, 'string'] })
      expect(parsed.items).toHaveLength(2)
    })
  })

  describe('EventSchema', () => {
    const base = {
      id: 'e1',
      title: 'Show',
      description: 'Desc',
      image: '/img.jpg',
      location: 'Local',
      time: '21:00',
    }

    it('accepts a minimal event', () => {
      expect(EventSchema.parse(base)).toMatchObject(base)
    })

    it('rejects missing required fields', () => {
      expect(() => EventSchema.parse({ ...base, title: undefined })).toThrow()
    })

    it('rejects wrong types', () => {
      expect(() => EventSchema.parse({ ...base, attendees: 'ten' })).toThrow()
    })
  })

  describe('validateAndConvertEvent', () => {
    const base = {
      id: 'e1',
      title: 'Show',
      description: 'Desc',
      image: '/img.jpg',
      location: 'Local',
      time: '21:00',
    }

    it('converts Date to millis', () => {
      const date = new Date('2025-03-01T12:00:00Z')
      const out = validateAndConvertEvent({ ...base, date })
      expect(out.date).toBe(date.getTime())
    })

    it('converts dd/MM/yyyy to millis', () => {
      const out = validateAndConvertEvent({ ...base, date: '15/03/2025' })
      expect(typeof out.date).toBe('number')
      const d = new Date(out.date as number)
      expect(d.getFullYear()).toBe(2025)
      expect(d.getMonth()).toBe(2)
      expect(d.getDate()).toBe(15)
    })

    it('leaves numeric date untouched', () => {
      const ms = 1_700_000_000_000
      expect(validateAndConvertEvent({ ...base, date: ms }).date).toBe(ms)
    })
  })
})
