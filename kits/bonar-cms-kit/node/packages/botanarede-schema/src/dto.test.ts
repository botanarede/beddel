import { describe, it, expect } from 'vitest';

import {
  PublicTenantConfigSchema,
  AdminTenantConfigSchema,
  PublicMetadataSchema,
  AdminMetadataSchema,
  toPublicDTO,
  toAdminDTO,
} from './dto';
import type { TenantConfig } from './tenant-config';

/** Minimal valid TenantConfig fixture */
function validConfig(): TenantConfig {
  return {
    metadata: {
      id: 'tenant-1',
      name: 'Test Tenant',
      status: 'active',
      domains: ['example.com'],
      publishedVersionId: 'v1',
      features: { darkMode: true },
    },
    designTokens: {},
    pages: {
      home: {
        route: '/',
        title: 'Home',
        layoutRef: 'public',
        sections: [{ type: 'hero', props: {} }],
        visibility: 'public',
      },
      admin: {
        route: '/admin',
        title: 'Admin Panel',
        layoutRef: 'admin',
        sections: [{ type: 'dashboard', props: {} }],
        visibility: 'admin',
      },
      about: {
        route: '/about',
        title: 'About',
        layoutRef: 'public',
        sections: [{ type: 'text', props: {} }],
      },
    },
    layouts: {
      public: { id: 'public', slots: [{ name: 'content' }] },
      admin: { id: 'admin', slots: [{ name: 'content' }] },
    },
    components: {
      hero: { type: 'hero', props: {} },
    },
    navigation: { menus: {} },
    features: { darkMode: true, betaFeature: false },
  };
}

describe('toPublicDTO', () => {
  it('returns object without features key', () => {
    const result = toPublicDTO(validConfig());
    expect(result).not.toHaveProperty('features');
  });

  it('returns PublicTenantConfig with correct metadata fields only', () => {
    const result = toPublicDTO(validConfig());
    expect(result.metadata).toEqual({
      id: 'tenant-1',
      name: 'Test Tenant',
      status: 'active',
      domains: ['example.com'],
      publishedVersionId: 'v1',
    });
    expect(result.metadata).not.toHaveProperty('features');
  });

  it('excludes pages with visibility: "admin"', () => {
    const result = toPublicDTO(validConfig());
    expect(result.pages).not.toHaveProperty('admin');
  });

  it('includes pages with visibility: "public" and pages with no visibility set', () => {
    const result = toPublicDTO(validConfig());
    expect(result.pages).toHaveProperty('home');
    expect(result.pages).toHaveProperty('about');
  });

  it('does not mutate the original config object', () => {
    const config = validConfig();
    const originalJson = JSON.stringify(config);
    toPublicDTO(config);
    expect(JSON.stringify(config)).toBe(originalJson);
  });

  it('result parses successfully with PublicTenantConfigSchema', () => {
    const result = toPublicDTO(validConfig());
    const parsed = PublicTenantConfigSchema.safeParse(result);
    expect(parsed.success).toBe(true);
  });
});

describe('toAdminDTO', () => {
  it('returns all original fields plus admin metadata', () => {
    const result = toAdminDTO(validConfig());
    expect(result.metadata.id).toBe('tenant-1');
    expect(result.designTokens).toBeDefined();
    expect(result.pages).toHaveProperty('home');
    expect(result.pages).toHaveProperty('admin');
    expect(result.features).toEqual({ darkMode: true, betaFeature: false });
  });

  it('merges draftStatus, lastEditor, lastEditedAt into metadata', () => {
    const result = toAdminDTO(validConfig(), {
      draftStatus: 'dirty',
      lastEditor: 'user@example.com',
      lastEditedAt: '2025-01-01T00:00:00Z',
    });
    expect(result.metadata.draftStatus).toBe('dirty');
    expect(result.metadata.lastEditor).toBe('user@example.com');
    expect(result.metadata.lastEditedAt).toBe('2025-01-01T00:00:00Z');
  });

  it('without optional admin meta still returns valid AdminTenantConfig', () => {
    const result = toAdminDTO(validConfig());
    const parsed = AdminTenantConfigSchema.safeParse(result);
    expect(parsed.success).toBe(true);
  });

  it('result parses successfully with AdminTenantConfigSchema', () => {
    const result = toAdminDTO(validConfig(), {
      draftStatus: 'clean',
      lastEditor: 'admin',
      lastEditedAt: '2025-06-01T12:00:00Z',
    });
    const parsed = AdminTenantConfigSchema.safeParse(result);
    expect(parsed.success).toBe(true);
  });

  it('does not mutate the original config object', () => {
    const config = validConfig();
    const originalJson = JSON.stringify(config);
    toAdminDTO(config, { draftStatus: 'dirty' });
    expect(JSON.stringify(config)).toBe(originalJson);
  });
});

describe('PublicTenantConfigSchema', () => {
  it('rejects objects with features key (strict)', () => {
    const publicDTO = toPublicDTO(validConfig());
    const withFeatures = { ...publicDTO, features: { darkMode: true } };
    const result = PublicTenantConfigSchema.safeParse(withFeatures);
    expect(result.success).toBe(false);
  });
});

describe('AdminTenantConfigSchema', () => {
  it('accepts objects with admin metadata fields', () => {
    const adminDTO = toAdminDTO(validConfig(), {
      draftStatus: 'pending-review',
      lastEditor: 'admin@test.com',
      lastEditedAt: '2025-01-15T10:30:00Z',
    });
    const result = AdminTenantConfigSchema.safeParse(adminDTO);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.metadata.draftStatus).toBe('pending-review');
      expect(result.data.metadata.lastEditor).toBe('admin@test.com');
      expect(result.data.metadata.lastEditedAt).toBe('2025-01-15T10:30:00Z');
    }
  });
});

describe('PublicMetadataSchema', () => {
  it('accepts valid public metadata', () => {
    const result = PublicMetadataSchema.safeParse({
      id: 'tenant-1',
      name: 'Test',
      status: 'active',
      domains: ['example.com'],
    });
    expect(result.success).toBe(true);
  });

  it('rejects metadata with features field', () => {
    const result = PublicMetadataSchema.safeParse({
      id: 'tenant-1',
      name: 'Test',
      status: 'active',
      domains: ['example.com'],
      features: { darkMode: true },
    });
    expect(result.success).toBe(false);
  });
});

describe('AdminMetadataSchema', () => {
  it('accepts metadata with admin-specific fields', () => {
    const result = AdminMetadataSchema.safeParse({
      id: 'tenant-1',
      name: 'Test',
      status: 'active',
      domains: ['example.com'],
      features: { darkMode: true },
      draftStatus: 'dirty',
      lastEditor: 'admin',
      lastEditedAt: '2025-01-01T00:00:00Z',
    });
    expect(result.success).toBe(true);
  });
});
