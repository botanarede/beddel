import type React from 'react';
import type { ComponentManifest } from './manifest';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ComponentMap = Record<string, React.ComponentType<any>>;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ComponentRegistry = Readonly<Record<string, React.ComponentType<any>>>;

export function buildRegistry(
  manifest: ComponentManifest,
  componentMap: ComponentMap,
): ComponentRegistry {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const result: Record<string, React.ComponentType<any>> = {};
  for (const type of Object.keys(manifest)) {
    const component = componentMap[type];
    if (component !== undefined) {
      result[type] = component;
    }
  }
  return Object.freeze(result);
}

export function resolveComponent(
  registry: ComponentRegistry,
  type: string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): React.ComponentType<any> | null {
  const component = registry[type];
  return component ?? null;
}
