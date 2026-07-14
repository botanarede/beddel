import { describe, it, expect } from 'vitest';
import { interpolate, interpolateProps } from './interpolation';

describe('interpolate', () => {
  it('resolves a single {{dot.path}} reference', () => {
    const ctx = { greeting: 'Hello' };
    expect(interpolate('{{greeting}} world', ctx)).toBe('Hello world');
  });

  it('resolves a nested path like {{tenant.name}}', () => {
    const ctx = { tenant: { name: 'Casa Savana' } };
    expect(interpolate('Welcome to {{tenant.name}}', ctx)).toBe('Welcome to Casa Savana');
  });

  it('resolves multiple references in one string', () => {
    const ctx = { page: { title: 'Home' }, tenant: { name: 'Casa Savana' } };
    expect(interpolate('{{page.title}} — {{tenant.name}}', ctx)).toBe('Home — Casa Savana');
  });

  it('leaves unresolved {{missing.key}} unchanged', () => {
    const ctx = { tenant: { name: 'Casa Savana' } };
    expect(interpolate('Hello {{missing.key}}', ctx)).toBe('Hello {{missing.key}}');
  });

  it('returns a number unchanged', () => {
    expect(interpolate(42, {})).toBe(42);
  });

  it('returns a boolean unchanged', () => {
    expect(interpolate(true, {})).toBe(true);
  });

  it('returns an object unchanged', () => {
    const obj = { nested: true };
    expect(interpolate(obj, {})).toBe(obj);
  });

  it('returns null unchanged', () => {
    expect(interpolate(null, {})).toBe(null);
  });

  it('returns undefined unchanged', () => {
    expect(interpolate(undefined, {})).toBe(undefined);
  });

  it('handles null value in context path gracefully', () => {
    const ctx = { a: null };
    expect(interpolate('{{a.b}}', ctx)).toBe('{{a.b}}');
  });

  it('does not traverse prototype properties', () => {
    const ctx = {};
    expect(interpolate('{{constructor.name}}', ctx)).toBe('{{constructor.name}}');
  });
});

describe('interpolateProps', () => {
  it('interpolates string props and passes through non-string props', () => {
    const props = {
      title: 'Welcome to {{tenant.name}}',
      count: 5,
      visible: true,
    };
    const ctx = { tenant: { name: 'Casa Savana' } };
    const result = interpolateProps(props, ctx);

    expect(result).toEqual({
      title: 'Welcome to Casa Savana',
      count: 5,
      visible: true,
    });
  });

  it('returns a new object (does not mutate input)', () => {
    const props = { title: '{{name}}' };
    const ctx = { name: 'Test' };
    const result = interpolateProps(props, ctx);

    expect(result).not.toBe(props);
    expect(props.title).toBe('{{name}}');
  });
});
