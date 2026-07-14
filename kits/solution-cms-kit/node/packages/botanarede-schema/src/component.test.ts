import { describe, it, expect } from 'vitest';

import { ComponentDefinitionSchema } from './component';

/** Minimal valid component object */
function validComponent(): Record<string, unknown> {
  return {
    type: 'hero',
    props: {},
  };
}

/** Return a copy of obj without the given key */
function omit(obj: Record<string, unknown>, key: string): Record<string, unknown> {
  const copy = { ...obj };
  delete copy[key];
  return copy;
}

describe('ComponentDefinitionSchema', () => {
  // AC#3: valid component with type and props parses
  it('parses a valid component with type and props', () => {
    const result = ComponentDefinitionSchema.parse(validComponent());
    expect(result.type).toBe('hero');
    expect(result.props).toEqual({});
  });

  // AC#3: component missing type fails
  it('fails when type is missing', () => {
    const result = ComponentDefinitionSchema.safeParse(omit(validComponent(), 'type'));
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['type']);
    }
  });

  // AC#5: type is a free-form string (not enum)
  it('accepts any string as type (not enum)', () => {
    const comp = { type: 'my-custom-fancy-widget-v3', props: {} };
    const result = ComponentDefinitionSchema.parse(comp);
    expect(result.type).toBe('my-custom-fancy-widget-v3');
  });

  // AC#3: optional children array with nested components parses
  it('parses optional children with nested components', () => {
    const comp = {
      type: 'container',
      props: { layout: 'flex' },
      children: [
        { type: 'heading', props: { text: 'Hello' } },
        {
          type: 'section',
          props: {},
          children: [{ type: 'paragraph', props: { content: 'Nested' } }],
        },
      ],
    };
    const result = ComponentDefinitionSchema.parse(comp);
    expect(result.children).toHaveLength(2);
    expect(result.children?.[1]?.children).toHaveLength(1);
  });

  // AC#3: props accepts arbitrary key-value pairs
  it('accepts arbitrary key-value pairs in props', () => {
    const comp = {
      type: 'card',
      props: {
        title: 'My Card',
        count: 42,
        enabled: true,
        nested: { deep: 'value' },
        items: [1, 2, 3],
      },
    };
    const result = ComponentDefinitionSchema.parse(comp);
    expect(result.props).toEqual({
      title: 'My Card',
      count: 42,
      enabled: true,
      nested: { deep: 'value' },
      items: [1, 2, 3],
    });
  });

  // AC#3: parses without children (optional)
  it('parses without children', () => {
    const result = ComponentDefinitionSchema.safeParse(validComponent());
    expect(result.success).toBe(true);
  });
});
