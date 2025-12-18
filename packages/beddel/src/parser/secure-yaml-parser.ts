import { load, FAILSAFE_SCHEMA } from 'js-yaml';
import { AllowedYamlPrimitive, YAMLParserConfig } from '../config';
import { YAMLParseError, YAMLSecurityError } from '../errors';

/**
 * Parser YAML seguro com FAILSAFE_SCHEMA e validações rigorosas
 * Preloading de módulos críticos realizada no construtor
 */
export class SecureYamlParser {
  private readonly config: YAMLParserConfig;
  
  constructor(config: YAMLParserConfig = {}) {
    this.config = this.validateAndMergeConfig(config);
  }

  /**
   * Valida e merge configuração com padrões seguros
   */
  private validateAndMergeConfig(userConfig: YAMLParserConfig): Required<YAMLParserConfig> {
    const defaultConfig: Required<YAMLParserConfig> = {
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
    const invalidTypes = merged.allowedTypes.filter((type: AllowedYamlPrimitive) => 
      !defaultConfig.allowedTypes.includes(type)
    );
    
    if (invalidTypes.length > 0) {
      throw new YAMLSecurityError(
        `Tipos não permitidos na FAILSAFE_SCHEMA: ${invalidTypes.join(', ')}`
      );
    }

    return merged;
  }

  /**
   * Parse YAML com segurança máxima usando FAILSAFE_SCHEMA
   */
  parseSecure(yamlContent: string): any {
    const startTime = performance.now();
    
    try {
      // Validar entrada
      this.validateInput(yamlContent);
      
      // Configurar opções de segurança para FAILSAFE_SCHEMA
      const parseOptions = this.buildSecureOptions();
      
      // Fazer parsing com FAILSAFE_SCHEMA
      const result = load(yamlContent, parseOptions);
      
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
      
    } catch (error) {
      if (error instanceof Error && error.name === 'YAMLException') {
        throw new YAMLParseError(`Erro ao fazer parse do YAML: ${error.message}`);
      }
      throw error;
    }
  }

  /**
   * Constrói opções de segurança para FAILSAFE_SCHEMA
   */
  private buildSecureOptions(): any {
    return {
      schema: FAILSAFE_SCHEMA,
      json: false,  // Desabilitar JSON mode para maior segurança
      onWarning: (warning: any) => {
        console.warn(`[SecureYamlParser] WARN: ${warning}`);
      },
      maxDepth: this.config.maxDepth,
      maxKeys: this.config.maxKeys,
      strict: this.config.strictMode,
      // Security hardening
      filename: this.config.filename || 'secure-parser',
      onError: (error: any) => {
        throw new YAMLSecurityError(`Erro de segurança durante parsing: ${error.message}`);
      }
    };
  }

  /**
   * Valida entrada antes do parsing
   */
  private validateInput(input: string): void {
    if (typeof input !== 'string') {
      throw new YAMLParseError('Input deve ser uma string');
    }
    
    const maxStringLength = this.config.maxStringLength || 1048576; // Default 1MB
    if (input.length > maxStringLength) {
      throw new YAMLSecurityError(
        `Tamanho do input (${input.length}) excede limite máximo (${maxStringLength})`
      );
    }
    
    if (input.trim().length === 0) {
      throw new YAMLParseError('Input vazio não é permitido');
    }
    
    // Validações UTF-8 básicas
    if ((this.config.validateUTF8 ?? true) && !this.isValidUTF8(input)) {
      throw new YAMLSecurityError('Input contém caracteres UTF-8 inválidos');
    }
  }

  /**
   * Valida resultado após parsing
   */
  private validateResult(result: any): void {
    // Validar profundidade máxima antes de serialização
    const depth = this.getObjectDepth(result);
    const maxDepth = this.config.maxDepth || 1000;
    if (depth > maxDepth) {
      throw new YAMLSecurityError(
        `Profundidade do objeto (${depth}) excede limite máximo (${maxDepth})`
      );
    }
    
    // Validar tipos permitidos
    if (!this.isAllowedType(result)) {
      const allowedTypes = this.config.allowedTypes || ['null', 'boolean', 'integer', 'float', 'string'];
      throw new YAMLSecurityError(
        'O resultado contém tipos não permitidos. Tipos permitidos: ' + 
        allowedTypes.join(', ')
      );
    }
    
    // Validar tamanho total aproximado
    const size = this.estimateObjectSize(result);
    const maxValueSize = this.config.maxValueSize || 10485760; // Default 10MB
    if (size > maxValueSize) {
      throw new YAMLSecurityError(
        `Tamanho do objeto (${size} bytes) excede limite máximo (${maxValueSize} bytes)`
      );
    }
  }

  /**
   * Verifica se é UTF-8 válido
   */
  private isValidUTF8(str: string): boolean {
    try {
      encodeURIComponent(str);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Calcula profundidade do objeto
   */
  private getObjectDepth(obj: any, currentDepth = 0): number {
    if (obj === null || typeof obj !== 'object') {
      return currentDepth;
    }
    
    if (Array.isArray(obj)) {
      return obj.reduce((max, item) => 
        Math.max(max as number, this.getObjectDepth(item, currentDepth + 1)), currentDepth + 1);
    }
    
    const values = Object.values(obj);
    return values.reduce((max: number, value) => 
      Math.max(max, this.getObjectDepth(value, currentDepth + 1)), currentDepth + 1);
  }

  /**
   * Verifica se os tipos são permitidos
   */
  private isAllowedType(obj: any): boolean {
    const type = this.getType(obj);
    
    // Verificar tipos básicos permitidos
    const allowedTypes = this.config.allowedTypes || ['null', 'boolean', 'integer', 'float', 'string'];
    if (!allowedTypes.includes(type as any)) {
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
  private estimateObjectSize(obj: any): number {
    return JSON.stringify(obj).length;
  }

  /**
   * Obtém tipo completo do objeto
   */
  private getType(obj: any): string {
    if (obj === null) return 'null';
    if (Array.isArray(obj)) return 'array';
    if (typeof obj === 'object') return 'object';
    if (typeof obj === 'number') {
      return Number.isInteger(obj) ? 'integer' : 'float';
    }
    return typeof obj;
  }

  /**
   * Parse assíncrono para lazy loading
   */
  async parseSecureAsync(yamlContent: string): Promise<any> {
    if (this.config.lazyLoading) {
      // Lazy loading - criar Promise para carregar parser apenas quando necessário
      return new Promise((resolve, reject) => {
        setTimeout(() => {
          try {
            resolve(this.parseSecure(yamlContent));
          } catch (error) {
            reject(error);
          }
        }, 0);
      });
    } else {
      return this.parseSecure(yamlContent);
    }
  }
}

/**
 * Factory function para criar parser com configuração padrão segura
 */
export function createSecureYamlParser(config?: Partial<YAMLParserConfig>): SecureYamlParser {
  return new SecureYamlParser(config);
}

/**
 * Função utilitária para parse rápido com configuração padrão
 */
export function parseSecureYaml(yamlContent: string, config?: Partial<YAMLParserConfig>): any {
  const parser = createSecureYamlParser(config);
  return parser.parseSecure(yamlContent);
}
