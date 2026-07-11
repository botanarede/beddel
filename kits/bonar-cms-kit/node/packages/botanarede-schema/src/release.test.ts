import { describe, it, expect } from 'vitest';

import {
  ReleaseMetadataSchema,
  isValidNextVersion,
} from './release';
import {
  computeChecksum,
  canonicalJson,
} from './release-checksum';
import type { TenantConfig } from './tenant-config';

/** Minimal valid TenantConfig fixture */
function validConfig(): TenantConfig {
  return {
    metadata: {
      id: 'tenant-1',
      name: 'Test Tenant',
      status: 'active',
      domains: ['example.com'],
    },
    designTokens: {},
    pages: {
      home: {
        route: '/',
        title: 'Home',
        layoutRef: 'public',
        sections: [{ type: 'hero', props: {} }],
      },
    },
    layouts: {
      public: {
        id: 'public',
        slots: [{ name: 'header' }, { name: 'content' }, { name: 'footer' }],
      },
    },
    components: {
      hero: { type: 'hero', props: {} },
    },
    navigation: { menus: {} },
  } as unknown as TenantConfig;
}

describe('computeChecksum', () => {
  it('returns a 64-character hex string (SHA-256)', () => {
    const result = computeChecksum(validConfig());
    expect(result).toMatch(/^[0-9a-f]{64}$/);
  });

  it('returns the same value for objects with identical content but different key order', () => {
    const a = validConfig();
    const raw = validConfig() as unknown as Record<string, unknown>;
    const reversed: Record<string, unknown> = {};
    const keys = Object.keys(raw).reverse();
    for (const k of keys) {
      reversed[k] = raw[k];
    }
    const b = reversed as unknown as TenantConfig;
    expect(computeChecksum(a)).toBe(computeChecksum(b));
  });

  it('returns different values for configs that differ by one field', () => {
    const a = validConfig();
    const b = validConfig();
    b.metadata = { ...b.metadata, name: 'Different Name' };
    expect(computeChecksum(a)).not.toBe(computeChecksum(b));
  });
});

describe('canonicalJson', () => {
  it('produces deterministic output for nested objects', () => {
    const a = { z: 1, a: { c: 3, b: 2 } };
    const b = { a: { b: 2, c: 3 }, z: 1 };
    expect(canonicalJson(a)).toBe(canonicalJson(b));
  });

  it('handles null and primitives', () => {
    expect(canonicalJson(null)).toBe('null');
    expect(canonicalJson(42)).toBe('42');
    expect(canonicalJson('hello')).toBe('"hello"');
    expect(canonicalJson(true)).toBe('true');
  });

  it('handles arrays preserving order', () => {
    expect(canonicalJson([3, 1, 2])).toBe('[3,1,2]');
  });
});

describe('ReleaseMetadataSchema', () => {
  it('parses valid metadata with integer versionId', () => {
    const result = ReleaseMetadataSchema.parse({
      versionId: 1,
      checksum: 'abc123',
      publishedAt: '2026-03-20T22:57:11.226Z',
      publishedBy: 'user-1',
    });
    expect(result.versionId).toBe(1);
  });

  it('parses valid metadata with semver string versionId', () => {
    const result = ReleaseMetadataSchema.parse({
      versionId: '1.0.0',
      checksum: 'abc123',
      publishedAt: '2026-03-20T22:57:11.226Z',
      publishedBy: 'user-1',
    });
    expect(result.versionId).toBe('1.0.0');
  });

  it('fails when publishedAt is not an ISO datetime string', () => {
    const result = ReleaseMetadataSchema.safeParse({
      versionId: 1,
      checksum: 'abc123',
      publishedAt: 'not-a-date',
      publishedBy: 'user-1',
    });
    expect(result.success).toBe(false);
  });

  it('fails when checksum is empty string', () => {
    const result = ReleaseMetadataSchema.safeParse({
      versionId: 1,
      checksum: '',
      publishedAt: '2026-03-20T22:57:11.226Z',
      publishedBy: 'user-1',
    });
    expect(result.success).toBe(false);
  });
});

describe('isValidNextVersion', () => {
  it('returns true for 1 -> 2', () => {
    expect(isValidNextVersion(1, 2)).toBe(true);
  });

  it('returns false for 2 -> 2 (same version)', () => {
    expect(isValidNextVersion(2, 2)).toBe(false);
  });

  it('returns false for 3 -> 2 (regression)', () => {
    expect(isValidNextVersion(3, 2)).toBe(false);
  });

  it('returns true for "1.0.0" -> "1.0.1"', () => {
    expect(isValidNextVersion('1.0.0', '1.0.1')).toBe(true);
  });

  it('returns false for "1.0.0" -> "1.0.0" (same)', () => {
    expect(isValidNextVersion('1.0.0', '1.0.0')).toBe(false);
  });

  it('returns false for "2.0.0" -> "1.9.9" (regression)', () => {
    expect(isValidNextVersion('2.0.0', '1.9.9')).toBe(false);
  });

  it('returns false for mixed types (number, string)', () => {
    expect(isValidNextVersion(1, '2.0.0')).toBe(false);
  });
});
