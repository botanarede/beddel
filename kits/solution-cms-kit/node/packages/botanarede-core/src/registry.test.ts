import { describe, it, expect } from 'vitest';
import type React from 'react';
import { createManifest } from './manifest';
import { buildRegistry, resolveComponent } from './registry';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const stubA = (() => null) as unknown as React.ComponentType<any>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const stubB = (() => null) as unknown as React.ComponentType<any>;

function makeManifest(types: string[]) {
  return createManifest(types.map((t) => ({ type: t, displayName: t, category: 'block' })));
}

describe('buildRegistry', () => {
  it('includes only types present in both manifest and componentMap', () => {
    const manifest = makeManifest(['hero', 'footer']);
    const registry = buildRegistry(manifest, { hero: stubA, footer: stubB });
    expect(Object.keys(registry)).toEqual(['hero', 'footer']);
    expect(registry['hero']).toBe(stubA);
    expect(registry['footer']).toBe(stubB);
  });

  it('excludes type present in manifest but absent from componentMap', () => {
    const manifest = makeManifest(['hero', 'footer']);
    const registry = buildRegistry(manifest, { hero: stubA });
    expect(Object.keys(registry)).toEqual(['hero']);
    expect(registry['footer']).toBeUndefined();
  });

  it('excludes type present in componentMap but absent from manifest', () => {
    const manifest = makeManifest(['hero']);
    const registry = buildRegistry(manifest, { hero: stubA, footer: stubB });
    expect(Object.keys(registry)).toEqual(['hero']);
    expect(registry['footer']).toBeUndefined();
  });
});

describe('resolveComponent', () => {
  it('returns the React component for a registered type', () => {
    const manifest = makeManifest(['hero']);
    const registry = buildRegistry(manifest, { hero: stubA });
    expect(resolveComponent(registry, 'hero')).toBe(stubA);
  });

  it('returns null for an unregistered type', () => {
    const manifest = makeManifest(['hero']);
    const registry = buildRegistry(manifest, { hero: stubA });
    expect(resolveComponent(registry, 'footer')).toBeNull();
  });
});

describe('registry immutability', () => {
  it('registry is frozen', () => {
    const manifest = makeManifest(['hero']);
    const registry = buildRegistry(manifest, { hero: stubA });
    expect(Object.isFrozen(registry)).toBe(true);
  });

  it('mutating frozen registry throws in strict mode', () => {
    const manifest = makeManifest(['hero']);
    const registry = buildRegistry(manifest, { hero: stubA });
    expect(() => {
      (registry as Record<string, unknown>)['hero'] = stubA;
    }).toThrow();
  });
});
