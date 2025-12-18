"use strict";
/**
 * Tipos de erro específicos para o parser YAML seguro
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.YAMLPerformanceError = exports.YAMLSecurityError = exports.YAMLParseError = exports.YAMLBaseError = void 0;
class YAMLBaseError extends Error {
    constructor(message, code) {
        super(message);
        this.code = code;
        this.name = 'YAMLBaseError';
        Object.setPrototypeOf(this, YAMLBaseError.prototype);
    }
}
exports.YAMLBaseError = YAMLBaseError;
class YAMLParseError extends YAMLBaseError {
    constructor(message, code) {
        super(message, code);
        this.name = 'YAMLParseError';
        Object.setPrototypeOf(this, YAMLParseError.prototype);
    }
}
exports.YAMLParseError = YAMLParseError;
class YAMLSecurityError extends YAMLBaseError {
    constructor(message, code) {
        super(message, code);
        this.name = 'YAMLSecurityError';
        Object.setPrototypeOf(this, YAMLSecurityError.prototype);
    }
}
exports.YAMLSecurityError = YAMLSecurityError;
class YAMLPerformanceError extends YAMLBaseError {
    constructor(message, code) {
        super(message, code);
        this.name = 'YAMLPerformanceError';
        Object.setPrototypeOf(this, YAMLPerformanceError.prototype);
    }
}
exports.YAMLPerformanceError = YAMLPerformanceError;
//# sourceMappingURL=errors.js.map