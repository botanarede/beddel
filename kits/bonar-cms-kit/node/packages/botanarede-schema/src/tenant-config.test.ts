import { describe, it, expect } from 'vitest';

import { TenantConfigSchema } from './tenant-config';
import type { TenantConfig } from './tenant-config';

/** Minimal valid config that satisfies all required fields */
function validConfig(): Record<string, unknown> {
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
  };
}

/** Return a copy of obj without the given key */
function omit(obj: Record<string, unknown>, key: string): Record<string, unknown> {
  const copy = { ...obj };
  delete copy[key];
  return copy;
}

describe('TenantConfigSchema', () => {
  it('has all 8 top-level keys', () => {
    const shape = TenantConfigSchema.shape;
    const keys = Object.keys(shape).sort();
    expect(keys).toEqual([
      'cacheConfig',
      'components',
      'designTokens',
      'features',
      'layouts',
      'metadata',
      'navigation',
      'pages',
    ]);
  });

  it('parses a valid minimal config', () => {
    const result = TenantConfigSchema.parse(validConfig());
    expect(result.metadata.id).toBe('tenant-1');
  });

  it('parses config with optional features', () => {
    const cfg = { ...validConfig(), features: { darkMode: true } };
    const result = TenantConfigSchema.parse(cfg);
    expect(result.features).toEqual({ darkMode: true });
  });

  it('fails when metadata is missing', () => {
    const result = TenantConfigSchema.safeParse(omit(validConfig(), 'metadata'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['metadata']);
    }
  });

  it('fails when designTokens is missing', () => {
    const result = TenantConfigSchema.safeParse(omit(validConfig(), 'designTokens'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['designTokens']);
    }
  });

  it('fails when navigation is missing', () => {
    const result = TenantConfigSchema.safeParse(omit(validConfig(), 'navigation'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['navigation']);
    }
  });

  it('fails when pages is missing', () => {
    const result = TenantConfigSchema.safeParse(omit(validConfig(), 'pages'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['pages']);
    }
  });

  it('fails when layouts is missing', () => {
    const result = TenantConfigSchema.safeParse(omit(validConfig(), 'layouts'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['layouts']);
    }
  });

  it('fails when components is missing', () => {
    const result = TenantConfigSchema.safeParse(omit(validConfig(), 'components'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['components']);
    }
  });

  it('inferred type works without any cast', () => {
    const cfg = TenantConfigSchema.parse(validConfig());
    const typed: TenantConfig = cfg;
    expect(typed.metadata.name).toBe('Test Tenant');
  });

  it('fails with path metadata.id when metadata.id is missing', () => {
    const cfg = validConfig();
    const meta = cfg.metadata as Record<string, unknown>;
    delete meta.id;
    const result = TenantConfigSchema.safeParse(cfg);
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['metadata', 'id']);
    }
  });

  it('parses without top-level features', () => {
    const cfg = validConfig();
    expect(cfg).not.toHaveProperty('features');
    const result = TenantConfigSchema.safeParse(cfg);
    expect(result.success).toBe(true);
  });
});
