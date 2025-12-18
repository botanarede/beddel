import { YAMLParserConfig } from '../config';
/**
 * Parser YAML seguro com FAILSAFE_SCHEMA e validações rigorosas
 * Preloading de módulos críticos realizada no construtor
 */
export declare class SecureYamlParser {
    private readonly config;
    constructor(config?: YAMLParserConfig);
    /**
     * Valida e merge configuração com padrões seguros
     */
    private validateAndMergeConfig;
    /**
     * Parse YAML com segurança máxima usando FAILSAFE_SCHEMA
     */
    parseSecure(yamlContent: string): any;
    /**
     * Constrói opções de segurança para FAILSAFE_SCHEMA
     */
    private buildSecureOptions;
    /**
     * Valida entrada antes do parsing
     */
    private validateInput;
    /**
     * Valida resultado após parsing
     */
    private validateResult;
    /**
     * Verifica se é UTF-8 válido
     */
    private isValidUTF8;
    /**
     * Calcula profundidade do objeto
     */
    private getObjectDepth;
    /**
     * Verifica se os tipos são permitidos
     */
    private isAllowedType;
    /**
     * Estima tamanho do objeto em bytes
     */
    private estimateObjectSize;
    /**
     * Obtém tipo completo do objeto
     */
    private getType;
    /**
     * Parse assíncrono para lazy loading
     */
    parseSecureAsync(yamlContent: string): Promise<any>;
}
/**
 * Factory function para criar parser com configuração padrão segura
 */
export declare function createSecureYamlParser(config?: Partial<YAMLParserConfig>): SecureYamlParser;
/**
 * Função utilitária para parse rápido com configuração padrão
 */
export declare function parseSecureYaml(yamlContent: string, config?: Partial<YAMLParserConfig>): any;
//# sourceMappingURL=secure-yaml-parser.d.ts.map