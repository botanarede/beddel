"use strict";
/**
 * Custom error classes shared across server runtimes.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.NotFoundError = exports.ExecutionError = exports.ValidationError = exports.RateLimitError = exports.AuthenticationError = void 0;
class AuthenticationError extends Error {
    constructor(message = "Authentication failed") {
        super(message);
        this.name = "AuthenticationError";
    }
}
exports.AuthenticationError = AuthenticationError;
class RateLimitError extends Error {
    constructor(message = "Rate limit exceeded") {
        super(message);
        this.name = "RateLimitError";
    }
}
exports.RateLimitError = RateLimitError;
class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}
exports.ValidationError = ValidationError;
class ExecutionError extends Error {
    constructor(message) {
        super(message);
        this.name = "ExecutionError";
    }
}
exports.ExecutionError = ExecutionError;
class NotFoundError extends Error {
    constructor(message) {
        super(message);
        this.name = "NotFoundError";
    }
}
exports.NotFoundError = NotFoundError;
//# sourceMappingURL=errors.js.map