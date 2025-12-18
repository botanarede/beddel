"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SecureYamlParser = void 0;
exports.createSecureYamlParser = createSecureYamlParser;
exports.parseSecureYaml = parseSecureYaml;
const js_yaml_1 = require("js-yaml");
const errors_1 = require("../errors");
/**
 * Parser YAML seguro com FAILSAFE_SCHEMA e validações rigorosas
 * Preloading de módulos críticos realizada no construtor
 */
class SecureYamlParser {
    constructor(config = {}) {
        this.config = this.validateAndMergeConfig(config);
    }
    /**
     * Valida e merge configuração com padrões seguros
     */
    validateAndMergeConfig(userConfig) {
        const defaultConfig = {
            schema: 'FAILSAFE_SCHEMA',
            allowedTypes: ['null', 'boolean', 'integer', 'float', 'string'],
            performanceTarget: 100,
            maxDepth: 1000,
            maxKeys: 10000,
            maxStringLength: 1024 * 1024, // 1MB
            maxValueSize: 10 * 1024 * 1024, // 10MB total
            lazyLoading: true,
            enableCaching: true,
            validateUTF8: true,
            strictMode: true,
            filename: 'secure-parser'
        };
        // Merge com configurações do usuário, validando tipos
        const merged = { ...defaultConfig, ...userConfig };
        // Validar tipos permitidos contra FAILSAFE_SCHEMA
        const invalidTypes = merged.allowedTypes.filter((type) => !defaultConfig.allowedTypes.includes(type));
        if (invalidTypes.length > 0) {
            throw new errors_1.YAMLSecurityError(`Tipos não permitidos na FAILSAFE_SCHEMA: ${invalidTypes.join(', ')}`);
        }
        return merged;
    }
    /**
     * Parse YAML com segurança máxima usando FAILSAFE_SCHEMA
     */
    parseSecure(yamlContent) {
        const startTime = performance.now();
        try {
            // Validar entrada
            this.validateInput(yamlContent);
            // Configurar opções de segurança para FAILSAFE_SCHEMA
            const parseOptions = this.buildSecureOptions();
            // Fazer parsing com FAILSAFE_SCHEMA
            const result = (0, js_yaml_1.load)(yamlContent, parseOptions);
            // Validar resultado
            this.validateResult(result);
            const endTime = performance.now();
            const parseTime = endTime - startTime;
            // Log performance se exceder target
            const target = this.config.performanceTarget || 100;
            if (parseTime > target) {
                console.warn(`[SecureYamlParser] Performance warning: ${parseTime}ms > ${target}ms target`);
            }
            return result;
        }
        catch (error) {
            if (error instanceof Error && error.name === 'YAMLException') {
                throw new errors_1.YAMLParseError(`Erro ao fazer parse do YAML: ${error.message}`);
            }
            throw error;
        }
    }
    /**
     * Constrói opções de segurança para FAILSAFE_SCHEMA
     */
    buildSecureOptions() {
        return {
            schema: js_yaml_1.FAILSAFE_SCHEMA,
            json: false, // Desabilitar JSON mode para maior segurança
            onWarning: (warning) => {
                console.warn(`[SecureYamlParser] WARN: ${warning}`);
            },
            maxDepth: this.config.maxDepth,
            maxKeys: this.config.maxKeys,
            strict: this.config.strictMode,
            // Security hardening
            filename: this.config.filename || 'secure-parser',
            onError: (error) => {
                throw new errors_1.YAMLSecurityError(`Erro de segurança durante parsing: ${error.message}`);
            }
        };
    }
    /**
     * Valida entrada antes do parsing
     */
    validateInput(input) {
        if (typeof input !== 'string') {
            throw new errors_1.YAMLParseError('Input deve ser uma string');
        }
        const maxStringLength = this.config.maxStringLength || 1048576; // Default 1MB
        if (input.length > maxStringLength) {
            throw new errors_1.YAMLSecurityError(`Tamanho do input (${input.length}) excede limite máximo (${maxStringLength})`);
        }
        if (input.trim().length === 0) {
            throw new errors_1.YAMLParseError('Input vazio não é permitido');
        }
        // Validações UTF-8 básicas
        if ((this.config.validateUTF8 ?? true) && !this.isValidUTF8(input)) {
            throw new errors_1.YAMLSecurityError('Input contém caracteres UTF-8 inválidos');
        }
    }
    /**
     * Valida resultado após parsing
     */
    validateResult(result) {
        // Validar profundidade máxima antes de serialização
        const depth = this.getObjectDepth(result);
        const maxDepth = this.config.maxDepth || 1000;
        if (depth > maxDepth) {
            throw new errors_1.YAMLSecurityError(`Profundidade do objeto (${depth}) excede limite máximo (${maxDepth})`);
        }
        // Validar tipos permitidos
        if (!this.isAllowedType(result)) {
            const allowedTypes = this.config.allowedTypes || ['null', 'boolean', 'integer', 'float', 'string'];
            throw new errors_1.YAMLSecurityError('O resultado contém tipos não permitidos. Tipos permitidos: ' +
                allowedTypes.join(', '));
        }
        // Validar tamanho total aproximado
        const size = this.estimateObjectSize(result);
        const maxValueSize = this.config.maxValueSize || 10485760; // Default 10MB
        if (size > maxValueSize) {
            throw new errors_1.YAMLSecurityError(`Tamanho do objeto (${size} bytes) excede limite máximo (${maxValueSize} bytes)`);
        }
    }
    /**
     * Verifica se é UTF-8 válido
     */
    isValidUTF8(str) {
        try {
            encodeURIComponent(str);
            return true;
        }
        catch {
            return false;
        }
    }
    /**
     * Calcula profundidade do objeto
     */
    getObjectDepth(obj, currentDepth = 0) {
        if (obj === null || typeof obj !== 'object') {
            return currentDepth;
        }
        if (Array.isArray(obj)) {
            return obj.reduce((max, item) => Math.max(max, this.getObjectDepth(item, currentDepth + 1)), currentDepth + 1);
        }
        const values = Object.values(obj);
        return values.reduce((max, value) => Math.max(max, this.getObjectDepth(value, currentDepth + 1)), currentDepth + 1);
    }
    /**
     * Verifica se os tipos são permitidos
     */
    isAllowedType(obj) {
        const type = this.getType(obj);
        // Verificar tipos básicos permitidos
        const allowedTypes = this.config.allowedTypes || ['null', 'boolean', 'integer', 'float', 'string'];
        if (!allowedTypes.includes(type)) {
            return false;
        }
        // Recursivamente verificar objetos e arrays
        if (typeof obj === 'object' && obj !== null) {
            const values = Array.isArray(obj) ? obj : Object.values(obj);
            return values.every(value => this.isAllowedType(value));
        }
        return true;
    }
    /**
     * Estima tamanho do objeto em bytes
     */
    estimateObjectSize(obj) {
        return JSON.stringify(obj).length;
    }
    /**
     * Obtém tipo completo do objeto
     */
    getType(obj) {
        if (obj === null)
            return 'null';
        if (Array.isArray(obj))
            return 'array';
        if (typeof obj === 'object')
            return 'object';
        if (typeof obj === 'number') {
            return Number.isInteger(obj) ? 'integer' : 'float';
        }
        return typeof obj;
    }
    /**
     * Parse assíncrono para lazy loading
     */
    async parseSecureAsync(yamlContent) {
        if (this.config.lazyLoading) {
            // Lazy loading - criar Promise para carregar parser apenas quando necessário
            return new Promise((resolve, reject) => {
                setTimeout(() => {
                    try {
                        resolve(this.parseSecure(yamlContent));
                    }
                    catch (error) {
                        reject(error);
                    }
                }, 0);
            });
        }
        else {
            return this.parseSecure(yamlContent);
        }
    }
}
exports.SecureYamlParser = SecureYamlParser;
/**
 * Factory function para criar parser com configuração padrão segura
 */
function createSecureYamlParser(config) {
    return new SecureYamlParser(config);
}
/**
 * Função utilitária para parse rápido com configuração padrão
 */
function parseSecureYaml(yamlContent, config) {
    const parser = createSecureYamlParser(config);
    return parser.parseSecure(yamlContent);
}
//# sourceMappingURL=secure-yaml-parser.js.map