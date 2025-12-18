"use strict";
/**
 * Security validation utilities for YAML parsing
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SecurityValidator = void 0;
exports.isSecureYamlObject = isSecureYamlObject;
const DEFAULT_VALIDATION_OPTIONS = {
    maxKeyLength: 1000,
    maxValueLength: 10485760, // 10MB
    maxTotalSize: 104857600, // 100MB
    validateKeyNames: true,
    restrictSpecialChars: true,
    maxNestingDepth: 1000
};
// Pattern para caracteres especiais perigosos
const DANGEROUS_CHARS_PATTERN = /[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]/;
const KEY_NAME_PATTERN = /^[a-zA-Z_][a-zA-Z0-9_\-]*$/;
class SecurityValidator {
    constructor(options = {}) {
        this.options = { ...DEFAULT_VALIDATION_OPTIONS, ...options };
    }
    /**
     * Valida um objeto ou valor YAML para segurança
     */
    validateObject(obj, path = 'root') {
        const errors = [];
        const warnings = [];
        const stats = {
            totalKeys: 0,
            maxDepth: 0,
            maxValueLength: 0,
            longestKey: '',
            dataTypes: {}
        };
        const visit = (current, currentPath, depth = 0) => {
            // Verifica profundidade máxima
            if (depth > this.options.maxNestingDepth) {
                errors.push({
                    type: 'depth_exceeded',
                    message: `Profundidade máxima de ${this.options.maxNestingDepth} excedida`,
                    path: currentPath,
                    severity: 'high'
                });
                return;
            }
            stats.maxDepth = Math.max(stats.maxDepth, depth);
            // Processa diferentes tipos de dados
            if (current === null || current === undefined) {
                stats.dataTypes.null = (stats.dataTypes.null || 0) + 1;
                return;
            }
            if (typeof current === 'boolean') {
                stats.dataTypes.boolean = (stats.dataTypes.boolean || 0) + 1;
                return;
            }
            if (typeof current === 'number') {
                stats.dataTypes.number = (stats.dataTypes.number || 0) + 1;
                return;
            }
            if (typeof current === 'string') {
                stats.dataTypes.string = (stats.dataTypes.string || 0) + 1;
                this.validateStringContent(current, currentPath, errors, warnings, stats);
                return;
            }
            if (Array.isArray(current)) {
                stats.dataTypes.array = (stats.dataTypes.array || 0) + 1;
                current.forEach((item, index) => {
                    visit(item, `${currentPath}[${index}]`, depth + 1);
                });
                return;
            }
            if (typeof current === 'object') {
                stats.dataTypes.object = (stats.dataTypes.object || 0) + 1;
                stats.totalKeys += Object.keys(current).length;
                for (const [key, value] of Object.entries(current)) {
                    this.validateKey(key, errors, warnings, stats);
                    visit(value, `${currentPath}.${key}`, depth + 1);
                }
                return;
            }
            // Tipo não permitido
            errors.push({
                type: 'forbidden_type',
                message: `Tipo de dado não permitido: ${typeof current}`,
                path: currentPath,
                severity: 'high'
            });
        };
        visit(obj, path, 0);
        // Adiciona warnings baseados nas estatísticas
        if (stats.totalKeys > 10000) {
            warnings.push({
                type: 'large_object',
                message: `Objeto com ${stats.totalKeys} chaves pode afetar performance`,
                path,
                recommendation: 'Considerar limitar número de chaves para objetos grandes'
            });
        }
        if (stats.maxDepth > 100) {
            warnings.push({
                type: 'deep_nesting',
                message: `Profundidade de ${stats.maxDepth} pode ser difícil de manter`,
                path,
                recommendation: 'Considerar reduzir níveis de aninhamento'
            });
        }
        return {
            valid: errors.length === 0,
            errors,
            warnings,
            stats
        };
    }
    /**
     * Valida o conteúdo de strings para caracteres perigosos
     */
    validateStringContent(str, path, errors, warnings, stats) {
        stats.maxValueLength = Math.max(stats.maxValueLength, str.length);
        // Verifica caracteres de controle perigosos
        if (DANGEROUS_CHARS_PATTERN.test(str)) {
            errors.push({
                type: 'dangerous_chars',
                message: 'String contém caracteres de controle perigosos',
                path,
                severity: 'high'
            });
        }
        // Verifica tentativas de injection
        if (this.options.restrictSpecialChars) {
            // Verifica padrões comuns de injection
            const dangerousPatterns = [
                /<script[^>]*>/i,
                /javascript:/i,
                /on\w+\s*=/i,
                /eval\s*\(/i,
                /expression\s*\(/i,
                /data:text\/html/i
            ];
            for (const pattern of dangerousPatterns) {
                if (pattern.test(str)) {
                    warnings.push({
                        type: 'potential_injection',
                        message: `Possível tentativa de code injection detectada`,
                        path,
                        recommendation: `Revisar conteúdo e filtrar elementos perigosos`
                    });
                }
            }
        }
        // Verifica tentativas de credential leakage
        const credentialPatterns = [
            /password\s*[:=]\s*["']?[\w\-]+["']?/i,
            /api[_-]?key\s*[:=]\s*["']?[\w\-]+["']?/i,
            /secret\s*[:=]\s*["']?[\w\-]+["']?/i,
            /token\s*[:=]\s*["']?[\w\-]+["']?/i
        ];
        for (const pattern of credentialPatterns) {
            if (pattern.test(str)) {
                warnings.push({
                    type: 'possible_credential',
                    message: `Possível exposição de credenciais detectada`,
                    path,
                    recommendation: `Remover ou mascarar informações sensíveis`
                });
                break;
            }
        }
    }
    /**
     * Valida nomes de chaves para garantir segurança
     */
    validateKey(key, errors, warnings, stats) {
        if (key.length > stats.longestKey.length) {
            stats.longestKey = key;
        }
        // Verifica tamanho da chave
        if (key.length > this.options.maxKeyLength) {
            errors.push({
                type: 'key_too_long',
                message: `Chave excede limite de ${this.options.maxKeyLength} caracteres`,
                path: `[key: "${key}"]`,
                severity: 'medium'
            });
            return;
        }
        // Valida formato do nome da chave
        if (this.options.validateKeyNames && !KEY_NAME_PATTERN.test(key)) {
            warnings.push({
                type: 'invalid_key_name',
                message: `Nome de chave "${key}" não segue convenções recomendadas`,
                path: `[key: "${key}"]`,
                recommendation: 'Usar nomes de chave alfanuméricos começando com letra ou underscore'
            });
        }
        // Verifica caracteres especiais na chave
        if (this.options.restrictSpecialChars && /[<>:"'&|]/.test(key)) {
            warnings.push({
                type: 'dangerous_key_chars',
                message: `Chave "${key}" contém caracteres potencialmente perigosos`,
                path: `[key: "${key}"]`,
                recommendation: 'Evitar caracteres especiais em nomes de chave'
            });
        }
    }
    /**
     * Gera um relatório de validação formatado
     */
    generateReport(result) {
        const lines = [];
        if (result.valid) {
            lines.push('✅ VALIDAÇÃO DE SEGURANÇA: PASS');
        }
        else {
            lines.push('❌ VALIDAÇÃO DE SEGURANÇA: FAIL');
        }
        lines.push('');
        if (result.errors.length > 0) {
            lines.push(`🔴 ERROS (${result.errors.length}):`);
            result.errors.forEach(error => {
                lines.push(`  ${error.path}: ${error.message} [${error.severity.toUpperCase()}]`);
            });
            lines.push('');
        }
        if (result.warnings.length > 0) {
            lines.push(`🟡 AVISOS (${result.warnings.length}):`);
            result.warnings.forEach(warning => {
                lines.push(`  ${warning.path}: ${warning.message}`);
                lines.push(`    💡 ${warning.recommendation}`);
            });
            lines.push('');
        }
        lines.push('📊 ESTATÍSTICAS:');
        lines.push(`  - Chaves totais: ${result.stats.totalKeys}`);
        lines.push(`  - Profundidade máxima: ${result.stats.maxDepth}`);
        lines.push(`  - Valor mais longo: ${result.stats.maxValueLength} caracteres`);
        lines.push(`  - Chave mais longa: "${result.stats.longestKey}" (${result.stats.longestKey.length} chars)`);
        lines.push('');
        lines.push('📈 TIPOS DE DADOS:');
        Object.entries(result.stats.dataTypes).forEach(([type, count]) => {
            lines.push(`  - ${type}: ${count}`);
        });
        return lines.join('\n');
    }
    /**
     * Cria um resumo rápido da validação
     */
    getQuickResult(result) {
        let score = 100;
        // Penalidades por erros
        result.errors.forEach(error => {
            switch (error.severity) {
                case 'low':
                    score -= 10;
                    break;
                case 'medium':
                    score -= 25;
                    break;
                case 'high':
                    score -= 50;
                    break;
                case 'critical':
                    score -= 100;
                    break;
            }
        });
        // Penalidades por warnings
        result.warnings.forEach(() => {
            score -= 5;
        });
        return {
            ok: result.valid,
            score: Math.max(0, score)
        };
    }
}
exports.SecurityValidator = SecurityValidator;
/**
 * Função auxiliar para validação rápida
 */
function isSecureYamlObject(obj, options = {}) {
    const validator = new SecurityValidator(options);
    const result = validator.validateObject(obj);
    return result.valid;
}
//# sourceMappingURL=validation.js.map