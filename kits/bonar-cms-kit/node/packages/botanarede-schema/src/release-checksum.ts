import { createHash } from 'node:crypto';

import type { TenantConfig } from './tenant-config';

/**
 * Recursively sorts object keys and produces a deterministic JSON string.
 * Guarantees identical output regardless of key insertion order.
 */
export function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return '[' + value.map(canonicalJson).join(',') + ']';
  }
  const sorted = Object.keys(value as Record<string, unknown>)
    .sort()
    .map((k) => {
      const v = (value as Record<string, unknown>)[k];
      return JSON.stringify(k) + ':' + canonicalJson(v);
    });
  return '{' + sorted.join(',') + '}';
}

/**
 * Computes a deterministic SHA-256 hex checksum of a TenantConfig.
 * Uses canonicalJson to ensure key-order independence.
 */
export function computeChecksum(config: TenantConfig): string {
  return createHash('sha256').update(canonicalJson(config)).digest('hex');
}
