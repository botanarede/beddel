import { describe, it, expect } from 'vitest';
import type { TenantConfig } from '@botanarede/schema';
import { resolvePage, resolveLayout, resolveSlots, resolvePageTree } from './resolver';

const config: TenantConfig = {
  metadata: { id: 'test', name: 'Test', status: 'active', domains: ['test.local'] },
  designTokens: {},
  pages: {
    home: {
      route: '/',
      title: 'Home',
      layoutRef: 'public',
      sections: [
        { type: 'hero-carousel', slot: 'main', props: { autoplay: true } },
        { type: 'next-events', slot: 'main', props: {} },
        { type: 'footer-cta', slot: 'footer', props: { text: 'Contact us' } },
      ],
    },
    agenda: {
      route: '/agenda',
      title: 'Agenda',
      layoutRef: 'public',
      sections: [
        { type: 'agenda-grid', slot: 'main', props: {} },
        { type: 'orphan-widget', slot: 'sidebar', props: {} },
      ],
    },
  },
  layouts: {
    public: {
      id: 'public',
      slots: [{ name: 'main' }, { name: 'footer' }],
    },
  },
  components: {},
  navigation: { menus: {} },
};

describe('resolvePage', () => {
  it('returns matching page for a known route', () => {
    const result = resolvePage(config, '/');
    expect(result).not.toBeNull();
    expect(result!.pageId).toBe('home');
    expect(result!.page.title).toBe('Home');
  });

  it('returns null for an unknown route', () => {
    expect(resolvePage(config, '/unknown')).toBeNull();
  });
});

describe('resolveLayout', () => {
  it('returns the layout referenced by page.layoutRef', () => {
    const page = config.pages['home']!;
    const layout = resolveLayout(config, page);
    expect(layout).not.toBeNull();
    expect(layout!.id).toBe('public');
  });

  it('returns null when layout ref does not exist', () => {
    const fakePage = { route: '/x', title: 'X', layoutRef: 'missing', sections: [] };
    expect(resolveLayout(config, fakePage)).toBeNull();
  });
});

describe('resolveSlots', () => {
  it('maps sections to their declared slots', () => {
    const layout = config.layouts['public']!;
    const page = config.pages['home']!;
    const slots = resolveSlots(layout, page);

    expect(slots['main']).toHaveLength(2);
    expect(slots['main']![0]!.type).toBe('hero-carousel');
    expect(slots['main']![1]!.type).toBe('next-events');
    expect(slots['footer']).toHaveLength(1);
    expect(slots['footer']![0]!.type).toBe('footer-cta');
  });

  it('places sections with unknown slot in "_unassigned"', () => {
    const layout = config.layouts['public']!;
    const page = config.pages['agenda']!;
    const slots = resolveSlots(layout, page);

    expect(slots['main']).toHaveLength(1);
    expect(slots['_unassigned']).toHaveLength(1);
    expect(slots['_unassigned']![0]!.type).toBe('orphan-widget');
  });

  it('places sections without slot property in "_unassigned"', () => {
    const layout = config.layouts['public']!;
    const page = {
      route: '/test',
      title: 'Test',
      layoutRef: 'public',
      sections: [{ type: 'no-slot-widget', props: {} }],
    };
    const slots = resolveSlots(layout, page);

    expect(slots['_unassigned']).toHaveLength(1);
    expect(slots['_unassigned']![0]!.type).toBe('no-slot-widget');
  });
});

describe('resolvePageTree', () => {
  it('returns full tree for a valid route', () => {
    const tree = resolvePageTree(config, '/');
    expect(tree).not.toBeNull();
    expect(tree!.page.title).toBe('Home');
    expect(tree!.layout).not.toBeNull();
    expect(tree!.layout!.id).toBe('public');
    expect(tree!.slots['main']).toHaveLength(2);
    expect(tree!.slots['footer']).toHaveLength(1);
  });

  it('returns null for unknown route', () => {
    expect(resolvePageTree(config, '/nope')).toBeNull();
  });

  it('returns layout: null and all sections in "_unassigned" when layout ref is invalid', () => {
    const badConfig: TenantConfig = {
      ...config,
      pages: {
        broken: {
          route: '/broken',
          title: 'Broken',
          layoutRef: 'nonexistent',
          sections: [
            { type: 'widget-a', slot: 'main', props: {} },
            { type: 'widget-b', props: {} },
          ],
        },
      },
    };
    const tree = resolvePageTree(badConfig, '/broken');
    expect(tree).not.toBeNull();
    expect(tree!.layout).toBeNull();
    expect(tree!.slots['_unassigned']).toHaveLength(2);
  });
});
