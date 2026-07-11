import { describe, it, expect } from 'vitest';

import {
  NavigationConfigSchema,
  NavItemSchema,
  validateRouteRefs,
} from './navigation';

// --- Helper: valid navigation config ---
function validNav() {
  return {
    menus: {
      main: {
        items: [
          { label: 'Home', type: 'route' as const, route: '/home' },
          { label: 'Google', type: 'external' as const, href: 'https://google.com' },
        ],
      },
    },
  };
}

describe('NavigationConfigSchema', () => {
  it('parses valid navigation with menus record', () => {
    const result = NavigationConfigSchema.safeParse(validNav());
    expect(result.success).toBe(true);
  });

  it('parses empty menus record', () => {
    const result = NavigationConfigSchema.safeParse({ menus: {} });
    expect(result.success).toBe(true);
  });

  it('rejects missing menus key', () => {
    const result = NavigationConfigSchema.safeParse({});
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['menus']);
    }
  });

  it('rejects unknown top-level keys', () => {
    const result = NavigationConfigSchema.safeParse({
      menus: {},
      unknownKey: 'should-fail',
    });
    expect(result.success).toBe(false);
  });
});

describe('NavItemSchema — route type', () => {
  it('parses route item with label and route', () => {
    const result = NavItemSchema.safeParse({
      label: 'Home',
      type: 'route',
      route: '/home',
    });
    expect(result.success).toBe(true);
  });

  it('rejects route item missing route field', () => {
    const result = NavItemSchema.safeParse({
      label: 'Home',
      type: 'route',
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['route']);
    }
  });
});

describe('NavItemSchema — external type', () => {
  it('parses external item with label and href', () => {
    const result = NavItemSchema.safeParse({
      label: 'Google',
      type: 'external',
      href: 'https://google.com',
    });
    expect(result.success).toBe(true);
  });

  it('rejects external item missing href field', () => {
    const result = NavItemSchema.safeParse({
      label: 'Google',
      type: 'external',
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['href']);
    }
  });
});

describe('NavItemSchema — hash type', () => {
  it('parses hash item with label and hash', () => {
    const result = NavItemSchema.safeParse({
      label: 'Section',
      type: 'hash',
      hash: '#about',
    });
    expect(result.success).toBe(true);
  });

  it('rejects hash item missing hash field', () => {
    const result = NavItemSchema.safeParse({
      label: 'Section',
      type: 'hash',
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['hash']);
    }
  });
});

describe('NavItemSchema — group type', () => {
  it('parses group item with children', () => {
    const result = NavItemSchema.safeParse({
      label: 'More',
      type: 'group',
      children: [
        { label: 'About', type: 'route', route: '/about' },
      ],
    });
    expect(result.success).toBe(true);
  });

  it('parses group with mixed child types', () => {
    const result = NavItemSchema.safeParse({
      label: 'More',
      type: 'group',
      children: [
        { label: 'About', type: 'route', route: '/about' },
        { label: 'Docs', type: 'external', href: 'https://docs.example.com' },
        { label: 'FAQ', type: 'hash', hash: '#faq' },
      ],
    });
    expect(result.success).toBe(true);
  });

  it('rejects nested group inside group children', () => {
    const result = NavItemSchema.safeParse({
      label: 'More',
      type: 'group',
      children: [
        {
          label: 'Nested',
          type: 'group',
          children: [{ label: 'Deep', type: 'route', route: '/deep' }],
        },
      ],
    });
    expect(result.success).toBe(false);
  });
});

describe('NavItemSchema — unknown type', () => {
  it('rejects item with unknown type', () => {
    const result = NavItemSchema.safeParse({
      label: 'Unknown',
      type: 'dropdown',
    });
    expect(result.success).toBe(false);
  });
});

describe('validateRouteRefs', () => {
  const pageRoutes = ['/home', '/about', '/contact'];

  it('returns empty array for valid route references', () => {
    const nav = NavigationConfigSchema.parse({
      menus: {
        main: {
          items: [
            { label: 'Home', type: 'route', route: '/home' },
            { label: 'About', type: 'route', route: '/about' },
            { label: 'Google', type: 'external', href: 'https://google.com' },
          ],
        },
      },
    });
    const errors = validateRouteRefs(nav, pageRoutes);
    expect(errors).toEqual([]);
  });

  it('returns errors for dangling route references', () => {
    const nav = NavigationConfigSchema.parse({
      menus: {
        main: {
          items: [
            { label: 'Home', type: 'route', route: '/home' },
            { label: 'Missing', type: 'route', route: '/nonexistent' },
          ],
        },
      },
    });
    const errors = validateRouteRefs(nav, pageRoutes);
    expect(errors).toHaveLength(1);
    expect(errors[0]!.itemLabel).toBe('Missing');
    expect(errors[0]!.route).toBe('/nonexistent');
    expect(errors[0]!.message).toContain('Dangling route reference');
  });

  it('detects dangling refs inside group children', () => {
    const nav = NavigationConfigSchema.parse({
      menus: {
        footer: {
          items: [
            {
              label: 'Links',
              type: 'group',
              children: [
                { label: 'Home', type: 'route', route: '/home' },
                { label: 'Ghost', type: 'route', route: '/ghost-page' },
              ],
            },
          ],
        },
      },
    });
    const errors = validateRouteRefs(nav, pageRoutes);
    expect(errors).toHaveLength(1);
    expect(errors[0]!.itemLabel).toBe('Ghost');
    expect(errors[0]!.route).toBe('/ghost-page');
  });
});
