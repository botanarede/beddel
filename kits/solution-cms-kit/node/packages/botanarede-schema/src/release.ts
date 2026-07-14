import { z } from 'zod';

// --- ReleaseMetadata Zod schema ---

export const VersionIdSchema = z.union([z.number().int().positive(), z.string().min(1)]);
export type VersionId = z.infer<typeof VersionIdSchema>;

export const ReleaseMetadataSchema = z.object({
  versionId: VersionIdSchema,
  checksum: z.string().min(1),
  publishedAt: z.string().datetime(),
  publishedBy: z.string().min(1),
}).strict();
export type ReleaseMetadata = z.infer<typeof ReleaseMetadataSchema>;

// --- isValidNextVersion ---

/**
 * Returns true only if `next` is strictly greater than `current`.
 * Supports integer and semver-style "major.minor.patch" strings.
 * Mixed types (one number, one string) always return false.
 */
export function isValidNextVersion(current: VersionId, next: VersionId): boolean {
  if (typeof current === 'number' && typeof next === 'number') {
    return next > current;
  }
  if (typeof current === 'string' && typeof next === 'string') {
    const a = current.split('.').map(Number);
    const b = next.split('.').map(Number);
    const len = Math.max(a.length, b.length);
    for (let i = 0; i < len; i++) {
      const av = a[i] ?? 0;
      const bv = b[i] ?? 0;
      if (bv > av) return true;
      if (bv < av) return false;
    }
    return false; // equal
  }
  return false; // mixed types
}
