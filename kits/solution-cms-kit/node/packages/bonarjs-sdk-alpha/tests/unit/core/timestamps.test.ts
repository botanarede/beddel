import { describe, expect, it, vi } from 'vitest'

import {
  TIMESTAMP_FIELDS,
  dateToMillis,
  nowMillis,
  sortByDate,
  startOfDayMillis,
  toDate,
} from '../../../src/core/utils/timestamps'

describe('core/utils/timestamps', () => {
  describe('toDate', () => {
    it('returns null for null / undefined', () => {
      expect(toDate(null)).toBeNull()
      expect(toDate(undefined)).toBeNull()
    })

    it('passes through valid Date instances', () => {
      const d = new Date('2025-01-01')
      expect(toDate(d)).toBe(d)
    })

    it('returns null for invalid Date instances', () => {
      expect(toDate(new Date(NaN))).toBeNull()
    })

    it('parses epoch milliseconds', () => {
      const ms = 1_700_000_000_000
      expect(toDate(ms)?.getTime()).toBe(ms)
    })

    it('parses ISO strings', () => {
      const iso = '2025-01-01T12:00:00Z'
      expect(toDate(iso)?.toISOString()).toBe('2025-01-01T12:00:00.000Z')
    })

    it('returns null for unparseable strings', () => {
      expect(toDate('not a date')).toBeNull()
    })

    it('returns null for unsupported types', () => {
      expect(toDate({})).toBeNull()
      expect(toDate([])).toBeNull()
      expect(toDate(true)).toBeNull()
    })
  })

  describe('dateToMillis', () => {
    it('returns the number unchanged', () => {
      expect(dateToMillis(1000)).toBe(1000)
    })
    it('converts Date to millis', () => {
      const d = new Date(2000)
      expect(dateToMillis(d)).toBe(2000)
    })
  })

  describe('nowMillis', () => {
    it('uses Date.now', () => {
      const spy = vi.spyOn(Date, 'now').mockReturnValue(42)
      expect(nowMillis()).toBe(42)
      spy.mockRestore()
    })
  })

  describe('startOfDayMillis', () => {
    it('returns midnight (local) for a given reference', () => {
      const d = new Date(2025, 0, 15, 13, 30, 45, 123)
      const out = new Date(startOfDayMillis(d))
      expect(out.getFullYear()).toBe(2025)
      expect(out.getHours()).toBe(0)
      expect(out.getMinutes()).toBe(0)
      expect(out.getSeconds()).toBe(0)
      expect(out.getMilliseconds()).toBe(0)
    })
  })

  describe('sortByDate', () => {
    it('sorts ascending by default', () => {
      const items = [
        { id: 'b', date: 2000 },
        { id: 'a', date: 1000 },
        { id: 'c', date: 3000 },
      ]
      const sorted = [...items].sort((a, b) => sortByDate(a, b))
      expect(sorted.map((i) => i.id)).toEqual(['a', 'b', 'c'])
    })

    it('sorts descending when requested', () => {
      const items = [
        { date: 1 },
        { date: 3 },
        { date: 2 },
      ]
      const sorted = [...items].sort((a, b) => sortByDate(a, b, 'date', 'desc'))
      expect(sorted.map((i) => i.date)).toEqual([3, 2, 1])
    })

    it('pushes entries without a valid date to the end', () => {
      const items = [
        { date: 'bad' },
        { date: 1000 },
      ]
      const sorted = [...items].sort((a, b) => sortByDate(a, b))
      expect(sorted[0]?.date).toBe(1000)
    })
  })

  it('exposes the canonical TIMESTAMP_FIELDS set', () => {
    expect(TIMESTAMP_FIELDS).toContain('createdAt')
    expect(TIMESTAMP_FIELDS).toContain('date')
    expect(TIMESTAMP_FIELDS).toContain('updatedAt')
  })
})
