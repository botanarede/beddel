/**
 * Interpolation engine for resolving {{variable}} references in component props.
 *
 * Resolves dot-path references like {{tenant.name}} against a context object.
 * Composes with token resolution: tokens ($colors.primary) run first,
 * then interpolation ({{tenant.name}}) runs second.
 */

/** Plain nested object used as interpolation context. */
export type InterpolationContext = Record<string, unknown>;

const INTERPOLATION_RE = /\{\{([^}]+)\}\}/g;

/**
 * Resolves a dot-separated path against a nested context object.
 * Returns undefined when the path does not exist.
 */
function resolvePath(context: InterpolationContext, path: string): unknown {
  const segments = path.split('.');
  let current: unknown = context;

  for (const segment of segments) {
    if (current === null || current === undefined || typeof current !== 'object') {
      return undefined;
    }
    if (!Object.prototype.hasOwnProperty.call(current, segment)) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[segment];
  }

  return current;
}

/**
 * Interpolates {{dot.path}} references in a template string.
 *
 * - Non-string values are returned unchanged.
 * - Unresolved placeholders remain as-is.
 * - Multiple references are resolved in a single pass.
 */
export function interpolate(template: unknown, context: InterpolationContext): unknown {
  if (typeof template !== 'string') {
    return template;
  }

  return template.replace(INTERPOLATION_RE, (match, path: string) => {
    const value = resolvePath(context, path.trim());
    return value !== undefined && value !== null ? String(value) : match;
  });
}

/**
 * Interpolates all string values in a props object (shallow map).
 *
 * Non-string values pass through unchanged. Returns a new object
 * (does not mutate input).
 */
export function interpolateProps(
  props: Record<string, unknown>,
  context: InterpolationContext,
): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, val] of Object.entries(props)) {
    result[key] = interpolate(val, context);
  }
  return result;
}
