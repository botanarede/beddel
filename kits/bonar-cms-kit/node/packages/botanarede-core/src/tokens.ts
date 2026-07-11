import type { DesignTokens } from '@botanarede/schema';

/**
 * Resolves a design token reference to its concrete CSS value.
 *
 * Token references start with "$" and use dot-separated paths:
 * - "$colors.primary" → tokens.colors.primary
 * - "$typography.fontSizes.lg" → tokens.typography.fontSizes.lg
 *
 * Non-token values (not starting with "$") are returned unchanged.
 * Returns undefined when the token path does not exist.
 */
export function resolveToken(tokens: DesignTokens, value: string): string | undefined {
  if (!value.startsWith('$')) {
    return value;
  }

  const path = value.slice(1).split('.');
  let current: unknown = tokens;

  for (const segment of path) {
    if (current === null || current === undefined || typeof current !== 'object') {
      return undefined;
    }
    current = (current as Record<string, unknown>)[segment];
  }

  return typeof current === 'string' ? current : undefined;
}

/**
 * Resolves all token references in a props object (shallow map).
 *
 * Each prop value is passed through resolveToken. If a token reference
 * cannot be resolved, the original token string is preserved.
 */
export function resolveTokensInProps(
  tokens: DesignTokens,
  props: Record<string, string>,
): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, val] of Object.entries(props)) {
    const resolved = resolveToken(tokens, val);
    result[key] = resolved ?? val;
  }
  return result;
}
