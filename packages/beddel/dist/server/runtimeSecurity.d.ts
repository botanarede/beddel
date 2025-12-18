/**
 * Security helpers used by the Next.js runtime and exported as part of the package.
 */
import type { ExecutionContext } from "./types";
/**
 * Sanitize user input to prevent code injection
 */
export declare function sanitizeInput(input: unknown): unknown;
/**
 * Validate method name (alphanumeric, underscores, and hyphens)
 */
export declare function isValidMethodName(name: string): boolean;
/**
 * Validate API key format
 */
export declare function isValidApiKey(apiKey: string): boolean;
/**
 * Execute stored code in a sandbox scope with a time limit.
 */
export declare function executeInSandbox(code: string, params: Record<string, unknown>, props: Record<string, string>, context: ExecutionContext): Promise<void>;
/**
 * Validate required props are provided
 */
export declare function validateRequiredProps(requiredProps: string[], providedProps: Record<string, string>): {
    valid: boolean;
    missing: string[];
};
//# sourceMappingURL=runtimeSecurity.d.ts.map