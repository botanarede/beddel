/**
 * Security validation utilities for YAML parsing
 */
export interface SecurityValidationOptions {
    maxKeyLength: number;
    maxValueLength: number;
    maxTotalSize: number;
    validateKeyNames: boolean;
    restrictSpecialChars: boolean;
    maxNestingDepth: number;
}
export interface ValidationResult {
    valid: boolean;
    errors: ValidationError[];
    warnings: ValidationWarning[];
    stats: ValidationStats;
}
export interface ValidationError {
    type: string;
    message: string;
    path: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
}
export interface ValidationWarning {
    type: string;
    message: string;
    path: string;
    recommendation: string;
}
export interface ValidationStats {
    totalKeys: number;
    maxDepth: number;
    maxValueLength: number;
    longestKey: string;
    dataTypes: Record<string, number>;
}
export declare class SecurityValidator {
    private readonly options;
    constructor(options?: Partial<SecurityValidationOptions>);
    /**
     * Valida um objeto ou valor YAML para segurança
     */
    validateObject(obj: any, path?: string): ValidationResult;
    /**
     * Valida o conteúdo de strings para caracteres perigosos
     */
    private validateStringContent;
    /**
     * Valida nomes de chaves para garantir segurança
     */
    private validateKey;
    /**
     * Gera um relatório de validação formatado
     */
    generateReport(result: ValidationResult): string;
    /**
     * Cria um resumo rápido da validação
     */
    getQuickResult(result: ValidationResult): {
        ok: boolean;
        score: number;
    };
}
/**
 * Função auxiliar para validação rápida
 */
declare function isSecureYamlObject(obj: any, options?: Partial<SecurityValidationOptions>): boolean;
export { isSecureYamlObject };
//# sourceMappingURL=validation.d.ts.map