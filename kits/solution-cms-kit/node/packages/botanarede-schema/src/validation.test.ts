import { describe, it, expect } from 'vitest';
import { validateTenantConfig } from './validation';

/**
 * Minimal valid TenantConfig fixture.
 * Every test clones and mutates this as needed.
 */
function validFixture() {
  return {
    metadata: {
      id: 'test-tenant',
      name: 'Test Tenant',
      status: 'active' as const,
      domains: ['test.example.com'],
    },
    designTokens: {},
    pages: {
      home: {
        route: '/',
        title: 'Home',
        layoutRef: 'default',
        sections: [{ type: 'hero', props: {} }],
      },
    },
    layouts: {
      default: {
        id: 'default',
        slots: [{ name: 'main' }],
      },
    },
    components: {
      hero: {
        type: 'hero',
        props: {},
      },
    },
    navigation: {
      menus: {
        main: {
          items: [{ label: 'Home', type: 'route' as const, route: '/' }],
        },
      },
    },
  };
}

describe('validateTenantConfig', () => {
  it('returns valid result for a valid config', () => {
    const result = validateTenantConfig(validFixture());
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
    expect(result.warnings).toEqual([]);
  });

  describe('structural stage', () => {
    it('returns structural error for missing required field', () => {
      const config = validFixture();
      const { metadata: _metadata, ...noMetadata } = config;
      void _metadata;

      const result = validateTenantConfig(noMetadata);
      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThanOrEqual(1);
      expect(result.errors.some((e) => e.stage === 'structural')).toBe(true);
    });

    it('returns structural error with path pointing to the field', () => {
      const config = validFixture();
      (config.metadata as Record<string, unknown>).status = 'invalid-status';

      const result = validateTenantConfig(config);
      expect(result.valid).toBe(false);
      expect(
        result.errors.some((e) => e.stage === 'structural' && e.path.includes('metadata')),
      ).toBe(true);
    });

    it('structural errors use "(root)" for root-level errors', () => {
      const result = validateTenantConfig(null);
      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThanOrEqual(1);
      expect(result.errors.some((e) => e.path === '(root)')).toBe(true);
    });

    it('structural errors have path set to field path', () => {
      const config = validFixture();
      const { id: _id, ...metaNoId } = config.metadata;
      void _id;
      (config as Record<string, unknown>).metadata = metaNoId;

      const result = validateTenantConfig(config);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.stage === 'structural' && e.path === 'metadata.id')).toBe(
        true,
      );
    });
  });

  describe('semantic stage', () => {
    it('returns semantic error for dangling layout reference', () => {
      const config = validFixture();
      config.pages.home.layoutRef = 'nonexistent';

      const result = validateTenantConfig(config);
      expect(result.valid).toBe(false);
      expect(
        result.errors.some((e) => e.stage === 'semantic' && e.path === 'pages.home.layoutRef'),
      ).toBe(true);
    });

    it('returns semantic error for dangling route reference', () => {
      const config = validFixture();
      config.navigation.menus.main.items = [
        { label: 'Missing', type: 'route' as const, route: '/nonexistent' },
      ];

      const result = validateTenantConfig(config);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.stage === 'semantic')).toBe(true);
    });

    it('collects semantic errors when structural passes', () => {
      const config = validFixture();
      config.pages.home.layoutRef = 'nonexistent';
      config.navigation.menus.main.items = [
        { label: 'Missing', type: 'route' as const, route: '/nonexistent' },
      ];

      const result = validateTenantConfig(config);
      expect(result.valid).toBe(false);
      const semanticErrors = result.errors.filter((e) => e.stage === 'semantic');
      expect(semanticErrors.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('manifest stage', () => {
    it('returns manifest warning for unknown component type', () => {
      const config = validFixture();
      const result = validateTenantConfig(config, {
        allowlist: ['other-type'],
      });

      expect(result.valid).toBe(true);
      expect(result.warnings.length).toBeGreaterThanOrEqual(1);
      expect(result.warnings.some((e) => e.stage === 'manifest' && e.severity === 'warning')).toBe(
        true,
      );
    });

    it('skips manifest stage when no allowlist provided', () => {
      const config = validFixture();
      config.components.hero.type = 'unknown-type';
      config.pages.home.sections[0] = { type: 'unknown-type', props: {} };

      const result = validateTenantConfig(config);
      expect(result.warnings).toEqual([]);
    });

    it('manifest warnings appear in warnings array not errors array', () => {
      const config = validFixture();
      const result = validateTenantConfig(config, {
        allowlist: ['other-type'],
      });

      expect(result.errors).toEqual([]);
      expect(result.warnings.length).toBeGreaterThanOrEqual(1);
      expect(result.warnings.every((w) => w.stage === 'manifest')).toBe(true);
    });
  });

  describe('orchestrator', () => {
    it('valid is false with error items, true with only warning items', () => {
      const config = validFixture();
      const warningResult = validateTenantConfig(config, {
        allowlist: ['other-type'],
      });
      expect(warningResult.valid).toBe(true);
      expect(warningResult.warnings.length).toBeGreaterThanOrEqual(1);

      const errorResult = validateTenantConfig(null);
      expect(errorResult.valid).toBe(false);
    });

    it('skips semantic and manifest when structural fails', () => {
      const config = {
        designTokens: {},
        pages: {
          home: {
            route: '/',
            title: 'Home',
            layoutRef: 'nonexistent',
            sections: [{ type: 'hero', props: {} }],
          },
        },
        layouts: {},
        components: { hero: { type: 'hero', props: {} } },
        navigation: {
          menus: {
            main: {
              items: [
                { label: 'Home', type: 'route', route: '/nonexistent' },
              ],
            },
          },
        },
      };

      const result = validateTenantConfig(config, {
        allowlist: ['other-type'],
      });

      expect(result.valid).toBe(false);
      expect(result.errors.every((e) => e.stage === 'structural')).toBe(true);
      expect(result.errors.some((e) => e.stage === 'semantic')).toBe(false);
      expect(result.warnings.some((w) => w.stage === 'manifest')).toBe(false);
    });
  });
});
