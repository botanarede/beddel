"use strict";
/**
 * Security helpers used by the Next.js runtime and exported as part of the package.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.sanitizeInput = sanitizeInput;
exports.isValidMethodName = isValidMethodName;
exports.isValidApiKey = isValidApiKey;
exports.executeInSandbox = executeInSandbox;
exports.validateRequiredProps = validateRequiredProps;
/**
 * Sanitize user input to prevent code injection
 */
function sanitizeInput(input) {
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
        const sanitized = {};
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
function isValidMethodName(name) {
    return /^[a-zA-Z_-][a-zA-Z0-9_.-]*$/.test(name);
}
/**
 * Validate API key format
 */
function isValidApiKey(apiKey) {
    return /^opal_[a-z0-9_-]+_key_[a-zA-Z0-9]{12,}$/.test(apiKey);
}
/**
 * Execute stored code in a sandbox scope with a time limit.
 */
async function executeInSandbox(code, params, props, context) {
    const executionPromise = (async () => {
        try {
            const executeFunction = new Function(`return ${code}`)();
            await executeFunction(params, props, context);
        }
        catch (error) {
            console.error("[Sandbox Execution Error]:", error);
            const errorMessage = error instanceof Error ? error.message : "Internal sandbox error";
            if (context.status !== "error") {
                context.setError(errorMessage);
            }
        }
    })();
    const timeoutPromise = new Promise((_, reject) => setTimeout(() => reject(new Error("Execution timed out after 3000ms")), 3000));
    try {
        await Promise.race([executionPromise, timeoutPromise]);
    }
    catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Unknown sandbox error";
        if (context.status !== "error") {
            context.setError(errorMessage);
        }
        context.log(`Sandbox execution failed: ${errorMessage}`);
    }
}
/**
 * Validate required props are provided
 */
function validateRequiredProps(requiredProps, providedProps) {
    const missing = requiredProps.filter((prop) => !providedProps[prop]);
    return {
        valid: missing.length === 0,
        missing,
    };
}
//# sourceMappingURL=runtimeSecurity.js.map