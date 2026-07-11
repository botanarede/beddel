import { describe, it, expect } from 'vitest';

import { TenantMetadataSchema } from './metadata';
import type { TenantMetadata } from './metadata';

/** Minimal valid metadata with all required fields */
function validMetadata(): Record<string, unknown> {
  return {
    id: 'tenant-1',
    name: 'Test Tenant',
    status: 'active',
    domains: ['example.com'],
  };
}

/** Return a copy of obj without the given key */
function omit(obj: Record<string, unknown>, key: string): Record<string, unknown> {
  const copy = { ...obj };
  delete copy[key];
  return copy;
}

describe('TenantMetadataSchema', () => {
  it('parses valid metadata with only required fields', () => {
    const result = TenantMetadataSchema.parse(validMetadata());
    expect(result.id).toBe('tenant-1');
    expect(result.name).toBe('Test Tenant');
    expect(result.status).toBe('active');
    expect(result.domains).toEqual(['example.com']);
  });

  it('parses metadata with all optional fields', () => {
    const full = {
      ...validMetadata(),
      publishedVersionId: 'v1.0.0',
      features: { darkMode: true, beta: false },
    };
    const result = TenantMetadataSchema.parse(full);
    expect(result.publishedVersionId).toBe('v1.0.0');
    expect(result.features).toEqual({ darkMode: true, beta: false });
  });

  // Inferred type compiles without any cast
  it('inferred TenantMetadata type works', () => {
    const typed: TenantMetadata = TenantMetadataSchema.parse(validMetadata());
    expect(typed.status).toBe('active');
  });

  // Required field validation — each required field individually
  it('fails when id is missing', () => {
    const result = TenantMetadataSchema.safeParse(omit(validMetadata(), 'id'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['id']);
    }
  });

  it('fails when name is missing', () => {
    const result = TenantMetadataSchema.safeParse(omit(validMetadata(), 'name'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['name']);
    }
  });

  it('fails when status is missing', () => {
    const result = TenantMetadataSchema.safeParse(omit(validMetadata(), 'status'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['status']);
    }
  });

  it('fails when domains is missing', () => {
    const result = TenantMetadataSchema.safeParse(omit(validMetadata(), 'domains'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['domains']);
    }
  });

  // Status enum validation
  it('rejects invalid status value', () => {
    const data = { ...validMetadata(), status: 'deleted' };
    const result = TenantMetadataSchema.safeParse(data);
    expect(result.success).toBe(false);
  });

  it('accepts all valid status values', () => {
    for (const status of ['active', 'inactive', 'suspended']) {
      const data = { ...validMetadata(), status };
      expect(TenantMetadataSchema.safeParse(data).success).toBe(true);
    }
  });

  // Optional fields are truly optional
  it('parses without publishedVersionId', () => {
    const data = validMetadata();
    expect(data).not.toHaveProperty('publishedVersionId');
    expect(TenantMetadataSchema.safeParse(data).success).toBe(true);
  });

  it('parses without features', () => {
    const data = validMetadata();
    expect(data).not.toHaveProperty('features');
    expect(TenantMetadataSchema.safeParse(data).success).toBe(true);
  });
});
