/**
 * Security hardening utilities for YAML parsing
 */
export interface SecurityHardeningOptions {
    maxCircularReferences: number;
    validateStructureIntegrity: boolean;
    enableContentInspection: boolean;
    logSecurityEvents: boolean;
    maxNestingDepth: number;
    enableCircularReferenceDetection: boolean;
    detectAndBlock: boolean;
    sanitizeOnFailure: boolean;
    validationPolicy: 'strict' | 'moderate' | 'lenient';
}
export interface SecurityEvent {
    timestamp: number;
    type: SecurityEventType;
    path: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    message: string;
    details?: any;
}
export type SecurityEventType = 'circular_reference' | 'deep_nesting' | 'oversized_object' | 'potential_injection' | 'invalid_structure' | 'content_inspection_warning' | 'schema_violation';
export interface StructureStats {
    maxDepth: number;
    totalKeys: number;
    circularReferences: number;
    uniqueObjects: number;
    totalSize: number;
    deepestPath: string;
}
export interface ContentIssue {
    path: string;
    type: string;
    severity: 'low' | 'medium' | 'high';
    description: string;
    pattern: string;
}
export interface SecurityHardeningStats {
    totalEvents: number;
    recentEvents: number;
    passes: number;
    fails: number;
    warnings: number;
    securityScore: number;
    eventsByType: Record<string, number>;
    recentAlerts: SecurityEvent[];
}
export declare class SecurityHardening {
    private readonly options;
    private events;
    private passes;
    private fails;
    private warnings;
    constructor(options?: Partial<SecurityHardeningOptions>);
    /**
     * Executa hardening completo em um objeto
     */
    harden(obj: any): {
        result: any;
        secure: boolean;
        stats: SecurityHardeningStats;
    };
    /**
     * Detecta referências circulares no objeto
     */
    detectCircularReferences(obj: any, visited?: WeakSet<object>, path?: string): void;
    /**
     * Valida a integridade estrutural do objeto
     */
    validateObjectStructure(obj: any): boolean;
    private isValidStructure;
    /**
     * Verifica se um tipo é permitido
     */
    private isAllowedType;
    /**
     * Inspeciona o conteúdo para padrões perigosos
     */
    inspectContent(obj: any): {
        issues: ContentIssue[];
        warnings: number;
    };
    /**
     * Sanitiza um objeto remover conteúdo potencialmente perigoso
     */
    sanitizeObject(obj: any): any;
    /**
     * Sanitiza strings removendo conteúdo perigoso
     */
    private sanitizeString;
    /**
     * Adiciona um evento de segurança
     */
    private addSecurityEvent;
    /**
     * Obtém estatísticas do hardening
     */
    getStatistics(): SecurityHardeningStats;
    /**
     * Calcula o score de segurança (0-100)
     */
    private calculateSecurityScore;
    /**
     * Agrupa eventos por tipo
     */
    private groupEventsByType;
    /**
     * Obtém alertas recentes
     */
    private getRecentAlerts;
    /**
     * Mapeia severidade para uso de eventos
     */
    private mapSeverity;
    /**
     * Reinicia as estatísticas
     */
    private resetStatistics;
    /**
     * Executa limpeza e validação final
     */
    cleanup(): void;
}
/**
 * Função auxiliar para criar instância de hardening
 */
declare function createSecurityHardening(options?: Partial<SecurityHardeningOptions>): SecurityHardening;
export { createSecurityHardening };
//# sourceMappingURL=hardening.d.ts.map