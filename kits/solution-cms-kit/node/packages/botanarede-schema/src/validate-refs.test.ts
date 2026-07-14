import { describe, it, expect } from 'vitest';

import { TenantConfigSchema } from './tenant-config';
import { validateLayoutRefs } from './validate-refs';

/** Build a minimal valid TenantConfig via schema parse */
function buildConfig(overrides: {
  pages?: Record<string, unknown>;
  layouts?: Record<string, unknown>;
} = {}) {
  return TenantConfigSchema.parse({
    metadata: {
      id: 'tenant-1',
      name: 'Test Tenant',
      status: 'active',
      domains: ['example.com'],
    },
    designTokens: {},
    pages: overrides.pages ?? {
      home: {
        route: '/',
        title: 'Home',
        layoutRef: 'public',
        sections: [{ type: 'hero', props: {} }],
      },
    },
    layouts: overrides.layouts ?? {
      public: {
        id: 'public',
        slots: [{ name: 'header' }, { name: 'content' }],
      },
    },
    components: {
      hero: { type: 'hero', props: {} },
    },
    navigation: { menus: {} },
  });
}

describe('validateLayoutRefs', () => {
  it('returns valid: true when all layout refs exist', () => {
    const config = buildConfig();
    const result = validateLayoutRefs(config);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('returns valid: false with descriptive error for dangling layout ref', () => {
    const config = buildConfig({
      pages: {
        about: {
          route: '/about',
          title: 'About',
          layoutRef: 'nonexistent-layout',
          sections: [],
        },
      },
      layouts: {
        public: {
          id: 'public',
          slots: [{ name: 'content' }],
        },
      },
    });
    const result = validateLayoutRefs(config);
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0]?.page).toBe('about');
    expect(result.errors[0]?.layoutRef).toBe('nonexistent-layout');
    expect(result.errors[0]?.message).toContain('nonexistent-layout');
    expect(result.errors[0]?.message).toContain('does not exist');
  });

  it('returns valid: true when there are no pages', () => {
    const config = buildConfig({
      pages: {},
      layouts: {
        public: {
          id: 'public',
          slots: [],
        },
      },
    });
    const result = validateLayoutRefs(config);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });
});
