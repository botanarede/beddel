import { describe, expect, it } from 'vitest'

import { generateSlug } from '../../../src/core/utils/slugify'

describe('core/utils/slugify', () => {
  it('returns empty string for empty input', () => {
    expect(generateSlug('')).toBe('')
  })

  it('strips diacritics', () => {
    expect(generateSlug('Café com Leite')).toBe('cafe-com-leite')
  })

  it('collapses runs of non-alphanumerics', () => {
    expect(generateSlug('Hello!!!  world???')).toBe('hello-world')
  })

  it('trims leading and trailing dashes', () => {
    expect(generateSlug('---foo---bar---')).toBe('foo-bar')
  })

  it('caps length at 100 chars', () => {
    const long = 'a'.repeat(150)
    expect(generateSlug(long).length).toBe(100)
  })

  it('does not leave a trailing dash after truncation', () => {
    const input = `${'a'.repeat(99)} word`
    const slug = generateSlug(input)
    expect(slug.endsWith('-')).toBe(false)
  })

  it('handles non-string input defensively', () => {
    // @ts-expect-error — deliberate bad input
    expect(generateSlug(42)).toBe('')
  })
})
