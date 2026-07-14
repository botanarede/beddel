import { describe, it, expect } from 'vitest';

import { LayoutDefinitionSchema, SlotDefinitionSchema } from './layout';

/** Minimal valid layout object */
function validLayout(): Record<string, unknown> {
  return {
    id: 'public',
    slots: [{ name: 'header' }, { name: 'content' }, { name: 'footer' }],
  };
}

/** Return a copy of obj without the given key */
function omit(obj: Record<string, unknown>, key: string): Record<string, unknown> {
  const copy = { ...obj };
  delete copy[key];
  return copy;
}

describe('LayoutDefinitionSchema', () => {
  // AC#2: valid layout with id, slots array parses successfully
  it('parses a valid layout with id and slots', () => {
    const result = LayoutDefinitionSchema.parse(validLayout());
    expect(result.id).toBe('public');
    expect(result.slots).toHaveLength(3);
  });

  // AC#2: layout missing id fails
  it('fails when id is missing', () => {
    const result = LayoutDefinitionSchema.safeParse(omit(validLayout(), 'id'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['id']);
    }
  });

  // AC#2: layout with empty slots array is valid
  it('accepts empty slots array', () => {
    const layout = { ...validLayout(), slots: [] };
    const result = LayoutDefinitionSchema.parse(layout);
    expect(result.slots).toHaveLength(0);
  });

  // AC#2: optional defaultProps accepted when present
  it('accepts optional defaultProps', () => {
    const layout = { ...validLayout(), defaultProps: { theme: 'dark', maxWidth: 1200 } };
    const result = LayoutDefinitionSchema.parse(layout);
    expect(result.defaultProps).toEqual({ theme: 'dark', maxWidth: 1200 });
  });

  // AC#2: parses without defaultProps (optional)
  it('parses without defaultProps', () => {
    const result = LayoutDefinitionSchema.safeParse(validLayout());
    expect(result.success).toBe(true);
  });
});

describe('SlotDefinitionSchema', () => {
  // AC#2: slot definition validates name field
  it('parses a valid slot with name', () => {
    const result = SlotDefinitionSchema.parse({ name: 'sidebar' });
    expect(result.name).toBe('sidebar');
  });

  it('fails when name is missing', () => {
    const result = SlotDefinitionSchema.safeParse({});
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['name']);
    }
  });

  it('accepts optional description', () => {
    const result = SlotDefinitionSchema.parse({ name: 'header', description: 'Top section' });
    expect(result.description).toBe('Top section');
  });
});
