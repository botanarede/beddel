/**
 * Custom error classes shared across server runtimes.
 */
export declare class AuthenticationError extends Error {
    constructor(message?: string);
}
export declare class RateLimitError extends Error {
    constructor(message?: string);
}
export declare class ValidationError extends Error {
    constructor(message: string);
}
export declare class ExecutionError extends Error {
    constructor(message: string);
}
export declare class NotFoundError extends Error {
    constructor(message: string);
}
//# sourceMappingURL=errors.d.ts.map