/**
 * Security helpers used by the Next.js runtime and exported as part of the package.
 */

import type { ExecutionContext } from "./types";

/**
 * Sanitize user input to prevent code injection
 */
export function sanitizeInput(input: unknown): unknown {
  if (typeof input === "string") {
    return input
      .replace(/[<>]/g, "")
      .replace(/javascript:/gi, "")
      .replace(/on\w+=/gi, "")
      .trim();
  }

  if (Array.isArray(input)) {
    return input.map(sanitizeInput);
  }

  if (typeof input === "object" && input !== null) {
    const sanitized: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(input)) {
      sanitized[key] = sanitizeInput(value);
    }
    return sanitized;
  }

  return input;
}

/**
 * Validate method name (alphanumeric, underscores, and hyphens)
 */
export function isValidMethodName(name: string): boolean {
  return /^[a-zA-Z_-][a-zA-Z0-9_.-]*$/.test(name);
}

/**
 * Validate API key format
 */
export function isValidApiKey(apiKey: string): boolean {
  return /^opal_[a-z0-9_-]+_key_[a-zA-Z0-9]{12,}$/.test(apiKey);
}

/**
 * Execute stored code in a sandbox scope with a time limit.
 */
export async function executeInSandbox(
  code: string,
  params: Record<string, unknown>,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<void> {
  const executionPromise = (async () => {
    try {
      const executeFunction = new Function(`return ${code}`)();
      await executeFunction(params, props, context);
    } catch (error) {
      console.error("[Sandbox Execution Error]:", error);
      const errorMessage =
        error instanceof Error ? error.message : "Internal sandbox error";
      if (context.status !== "error") {
        context.setError(errorMessage);
      }
    }
  })();

  const timeoutPromise = new Promise<void>((_, reject) =>
    setTimeout(
      () => reject(new Error("Execution timed out after 3000ms")),
      3000
    )
  );

  try {
    await Promise.race([executionPromise, timeoutPromise]);
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown sandbox error";
    if (context.status !== "error") {
      context.setError(errorMessage);
    }
    context.log(`Sandbox execution failed: ${errorMessage}`);
  }
}

/**
 * Validate required props are provided
 */
export function validateRequiredProps(
  requiredProps: string[],
  providedProps: Record<string, string>
): { valid: boolean; missing: string[] } {
  const missing = requiredProps.filter((prop) => !providedProps[prop]);
  return {
    valid: missing.length === 0,
    missing,
  };
}
