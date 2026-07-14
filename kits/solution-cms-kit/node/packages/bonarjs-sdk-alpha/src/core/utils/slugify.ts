const MAX_SLUG_LENGTH = 100

/**
 * Generate a URL-safe slug from a human-readable title.
 *
 * - Strips diacritics via Unicode normalization.
 * - Lowercases everything.
 * - Replaces runs of non-alphanumeric characters with a single dash.
 * - Trims leading/trailing dashes and caps the output at 100 characters.
 *
 * @param title — arbitrary title text.
 * @returns The slug; empty string when no meaningful characters remain.
 */
export function generateSlug(title: string): string {
  if (typeof title !== 'string' || title.length === 0) return ''

  const withoutAccents = title
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')

  const slug = withoutAccents
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')

  if (slug.length <= MAX_SLUG_LENGTH) return slug

  return slug.slice(0, MAX_SLUG_LENGTH).replace(/-+$/g, '')
}
