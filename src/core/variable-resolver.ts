/**
 * Beddel Protocol - Variable Resolver
 * 
 * Resolves template variables in step configurations.
 * Patterns: $input.path.to.value, $stepResult.path.to.value
 * 
 * Server-only: Used within WorkflowExecutor during step execution.
 */

import type { ExecutionContext } from '../types';

/**
 * Resolve a path like "foo.bar.baz" on an object.
 * Returns undefined if path doesn't exist.
 */
function resolvePath(obj: unknown, path: string): unknown {
    const parts = path.split('.');
    let current: unknown = obj;

    for (const part of parts) {
        if (current === null || current === undefined) {
            return undefined;
        }
        if (typeof current === 'object') {
            current = (current as Record<string, unknown>)[part];
        } else {
            return undefined;
        }
    }

    return current;
}

/**
 * Interpolate variable references within a string.
 * Replaces $input.*, $stepResult.*, and $varName.* patterns.
 * 
 * @param template - String containing variable references
 * @param context - Execution context
 * @returns String with variables replaced by their values
 */
function interpolateVariables(template: string, context: ExecutionContext): string {
    // Pattern to match $input.path, $stepResult.varName.path, or $varName.path
    // Matches: $word.word.word... (stops at whitespace, newline, or end)
    const variablePattern = /\$([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)/g;

    return template.replace(variablePattern, (match, fullPath: string) => {
        // Handle $input.* pattern
        if (fullPath.startsWith('input.')) {
            const path = fullPath.slice(6); // Remove "input."
            const value = resolvePath(context.input, path);
            return value !== undefined ? String(value) : match;
        }

        // Handle $stepResult.* pattern
        if (fullPath.startsWith('stepResult.')) {
            const restPath = fullPath.slice(11); // Remove "stepResult."
            const dotIndex = restPath.indexOf('.');

            if (dotIndex === -1) {
                const value = context.variables.get(restPath);
                return value !== undefined ? String(value) : match;
            }

            const varName = restPath.slice(0, dotIndex);
            const valuePath = restPath.slice(dotIndex + 1);
            const varValue = context.variables.get(varName);
            const value = resolvePath(varValue, valuePath);
            return value !== undefined ? String(value) : match;
        }

        // Handle legacy $varName.* pattern
        const dotIndex = fullPath.indexOf('.');
        if (dotIndex === -1) {
            const value = context.variables.get(fullPath);
            return value !== undefined ? String(value) : match;
        }

        const varName = fullPath.slice(0, dotIndex);
        const valuePath = fullPath.slice(dotIndex + 1);
        const varValue = context.variables.get(varName);
        const value = resolvePath(varValue, valuePath);
        return value !== undefined ? String(value) : match;
    });
}

/**
 * Resolve variable references in a template value.
 * 
 * Supports:
 * - "$input.messages" → context.input.messages
 * - "$stepResult.llmOutput.text" → context.variables.get('llmOutput').text
 * - Nested objects/arrays are resolved recursively
 * 
 * @param template - Value to resolve (string, object, array, or primitive)
 * @param context - Execution context with input and variables
 * @returns Resolved value with all variable references replaced
 */
export function resolveVariables(template: unknown, context: ExecutionContext): unknown {
    // Handle null/undefined
    if (template === null || template === undefined) {
        return template;
    }

    // Handle string patterns
    if (typeof template === 'string') {
        // Check if entire string is a single variable reference
        // Check for $input.* pattern (entire string)
        if (template.startsWith('$input.') && !template.includes(' ') && !template.includes('\n')) {
            const path = template.slice(7); // Remove "$input."
            return resolvePath(context.input, path);
        }

        // Check for $stepResult.* pattern (entire string)
        if (template.startsWith('$stepResult.') && !template.includes(' ') && !template.includes('\n')) {
            const fullPath = template.slice(12); // Remove "$stepResult."
            const dotIndex = fullPath.indexOf('.');

            if (dotIndex === -1) {
                return context.variables.get(fullPath);
            }

            const varName = fullPath.slice(0, dotIndex);
            const restPath = fullPath.slice(dotIndex + 1);
            const varValue = context.variables.get(varName);
            return resolvePath(varValue, restPath);
        }

        // Check for legacy $varName.* pattern (entire string)
        if (template.startsWith('$') && !template.startsWith('$$') && !template.includes(' ') && !template.includes('\n')) {
            const fullPath = template.slice(1); // Remove "$"
            const dotIndex = fullPath.indexOf('.');

            if (dotIndex === -1) {
                return context.variables.get(fullPath);
            }

            const varName = fullPath.slice(0, dotIndex);
            const restPath = fullPath.slice(dotIndex + 1);
            const varValue = context.variables.get(varName);
            return resolvePath(varValue, restPath);
        }

        // String interpolation: replace $variable.path patterns within larger strings
        if (template.includes('$')) {
            return interpolateVariables(template, context);
        }

        // No pattern match, return as-is
        return template;
    }

    // Handle arrays - resolve each element
    if (Array.isArray(template)) {
        return template.map(item => resolveVariables(item, context));
    }

    // Handle objects - resolve each value
    if (typeof template === 'object') {
        const resolved: Record<string, unknown> = {};
        for (const [key, value] of Object.entries(template)) {
            resolved[key] = resolveVariables(value, context);
        }
        return resolved;
    }

    // Primitives (number, boolean) - return as-is
    return template;
}
