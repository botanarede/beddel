/**
 * Tipos de erro específicos para o parser YAML seguro
 */
export declare class YAMLBaseError extends Error {
    code?: string | undefined;
    constructor(message: string, code?: string | undefined);
}
export declare class YAMLParseError extends YAMLBaseError {
    constructor(message: string, code?: string);
}
export declare class YAMLSecurityError extends YAMLBaseError {
    constructor(message: string, code?: string);
}
export declare class YAMLPerformanceError extends YAMLBaseError {
    constructor(message: string, code?: string);
}
//# sourceMappingURL=errors.d.ts.map