import { describe, it, expect } from 'vitest';
import type { TenantConfig } from '@botanarede/schema';
import {
  createManifest,
  isAllowed,
  validateManifestCompatibility,
  type ManifestEntry,
} from './manifest';

const heroEntry: ManifestEntry = {
  type: 'hero-carousel',
  displayName: 'Hero Carousel',
  category: 'hero',
  allowedSlots: ['main'],
};

const cardEntry: ManifestEntry = {
  type: 'info-card',
  displayName: 'Info Card',
  category: 'content',
};

function makeConfig(
  overrides: {
    components?: TenantConfig['components'];
    pages?: TenantConfig['pages'];
  } = {},
): TenantConfig {
  return {
    metadata: {
      id: 'test-tenant',
      name: 'Test Tenant',
      status: 'active',
      domains: ['test.localhost'],
    },
    designTokens: {},
    layouts: {},
    components: overrides.components ?? {},
    pages: overrides.pages ?? {},
    navigation: { menus: {} },
  };
}

describe('createManifest', () => {
  it('builds a record keyed by entry.type', () => {
    const manifest = createManifest([heroEntry, cardEntry]);
    expect(Object.keys(manifest)).toEqual(['hero-carousel', 'info-card']);
    expect(manifest['hero-carousel']).toEqual(heroEntry);
    expect(manifest['info-card']).toEqual(cardEntry);
  });
});

describe('ManifestEntry shape', () => {
  it('has required fields type, displayName, category', () => {
    expect(heroEntry).toHaveProperty('type');
    expect(heroEntry).toHaveProperty('displayName');
    expect(heroEntry).toHaveProperty('category');
  });

  it('allowedSlots and propsSchema are optional', () => {
    expect(cardEntry.allowedSlots).toBeUndefined();
    expect(cardEntry.propsSchema).toBeUndefined();
    expect(heroEntry.allowedSlots).toEqual(['main']);
  });
});

describe('isAllowed', () => {
  const manifest = createManifest([heroEntry, cardEntry]);

  it('returns true for a type present in the manifest', () => {
    expect(isAllowed(manifest, 'hero-carousel')).toBe(true);
  });

  it('returns false for a type absent from the manifest', () => {
    expect(isAllowed(manifest, 'unknown-widget')).toBe(false);
  });

  it('returns false for an empty manifest (deny-all default)', () => {
    const empty = createManifest([]);
    expect(isAllowed(empty, 'any-type')).toBe(false);
  });
});

describe('validateManifestCompatibility', () => {
  const manifest = createManifest([heroEntry, cardEntry]);

  it('returns empty array when all types in config are in manifest', () => {
    const config = makeConfig({
      components: {
        hero: { type: 'hero-carousel', props: {} },
      },
      pages: {
        home: {
          route: '/',
          title: 'Home',
          layoutRef: 'default',
          sections: [{ type: 'info-card', props: {} }],
        },
      },
    });
    expect(validateManifestCompatibility(manifest, config)).toEqual([]);
  });

  it('returns one entry per unknown type from config.components', () => {
    const config = makeConfig({
      components: {
        widget: { type: 'fancy-widget', props: {} },
      },
    });
    const result = validateManifestCompatibility(manifest, config);
    expect(result).toHaveLength(1);
    expect(result[0]!.type).toBe('fancy-widget');
    expect(result[0]!.message).toContain('fancy-widget');
  });

  it('returns one entry per unknown type from config.pages[*].sections', () => {
    const config = makeConfig({
      pages: {
        about: {
          route: '/about',
          title: 'About',
          layoutRef: 'default',
          sections: [{ type: 'unknown-section', props: {} }],
        },
      },
    });
    const result = validateManifestCompatibility(manifest, config);
    expect(result).toHaveLength(1);
    expect(result[0]!.type).toBe('unknown-section');
  });

  it('deduplicates — same unknown type from both sources appears once', () => {
    const config = makeConfig({
      components: {
        dup: { type: 'missing-type', props: {} },
      },
      pages: {
        home: {
          route: '/',
          title: 'Home',
          layoutRef: 'default',
          sections: [{ type: 'missing-type', props: {} }],
        },
      },
    });
    const result = validateManifestCompatibility(manifest, config);
    expect(result).toHaveLength(1);
    expect(result[0]!.type).toBe('missing-type');
  });
});
