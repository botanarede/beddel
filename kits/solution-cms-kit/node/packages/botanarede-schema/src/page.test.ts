import { describe, it, expect } from 'vitest';

import { PageDefinitionSchema, SectionSchema } from './page';

/** Minimal valid page object */
function validPage(): Record<string, unknown> {
  return {
    route: '/home',
    title: 'Home Page',
    layoutRef: 'public',
    sections: [{ type: 'hero', props: {} }],
  };
}

/** Return a copy of obj without the given key */
function omit(obj: Record<string, unknown>, key: string): Record<string, unknown> {
  const copy = { ...obj };
  delete copy[key];
  return copy;
}

describe('PageDefinitionSchema', () => {
  it('parses a valid page with all required fields', () => {
    const result = PageDefinitionSchema.parse(validPage());
    expect(result.route).toBe('/home');
    expect(result.title).toBe('Home Page');
    expect(result.layoutRef).toBe('public');
    expect(result.sections).toHaveLength(1);
  });

  it('fails when route is missing', () => {
    const result = PageDefinitionSchema.safeParse(omit(validPage(), 'route'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['route']);
    }
  });

  it('fails when layoutRef is missing', () => {
    const result = PageDefinitionSchema.safeParse(omit(validPage(), 'layoutRef'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['layoutRef']);
    }
  });

  it('parses sections array with multiple component references', () => {
    const page = {
      ...validPage(),
      sections: [
        { type: 'hero', props: { heading: 'Welcome' } },
        { type: 'features', slot: 'content', props: { columns: 3 } },
      ],
    };
    const result = PageDefinitionSchema.parse(page);
    expect(result.sections).toHaveLength(2);
    expect(result.sections[1]?.slot).toBe('content');
  });

  it('accepts any string as section type (not enum)', () => {
    const page = {
      ...validPage(),
      sections: [{ type: 'my-custom-widget-v2', props: {} }],
    };
    const result = PageDefinitionSchema.parse(page);
    expect(result.sections[0]?.type).toBe('my-custom-widget-v2');
  });

  it('parses without visibility (optional)', () => {
    const result = PageDefinitionSchema.safeParse(validPage());
    expect(result.success).toBe(true);
  });

  it('accepts visibility "public"', () => {
    const page = { ...validPage(), visibility: 'public' };
    const result = PageDefinitionSchema.parse(page);
    expect(result.visibility).toBe('public');
  });

  it('accepts visibility "admin"', () => {
    const page = { ...validPage(), visibility: 'admin' };
    const result = PageDefinitionSchema.parse(page);
    expect(result.visibility).toBe('admin');
  });

  it('rejects invalid visibility value', () => {
    const page = { ...validPage(), visibility: 'superuser' };
    const result = PageDefinitionSchema.safeParse(page);
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['visibility']);
    }
  });
});

describe('SectionSchema', () => {
  it('accepts any string as type', () => {
    const result = SectionSchema.parse({ type: 'arbitrary-component', props: {} });
    expect(result.type).toBe('arbitrary-component');
  });

  it('accepts optional slot field', () => {
    const result = SectionSchema.parse({ type: 'hero', slot: 'header', props: {} });
    expect(result.slot).toBe('header');
  });
});
