/**
 * Audit service for Isolated Runtime - comprehensive audit trail
 * Integration with story 1.1 SHA-256 logging system
 */
declare class EventEmitterBase {
    private listeners;
    emit(event: string, ...args: any[]): void;
    on(event: string, listener: (...args: any[]) => any): void;
}
export interface AuditEvent {
    id: string;
    timestamp: number;
    type: AuditEventType;
    executionId: string;
    tenantId: string;
    userId?: string;
    action: string;
    resource: string;
    details: Record<string, any>;
    result: "success" | "failure";
    severity: "low" | "medium" | "high" | "critical";
    sourceIp?: string;
    userAgent?: string;
    checksum: string;
    signature?: string;
}
export type AuditEventType = "EXECUTION_START" | "EXECUTION_END" | "SECURITY_VIOLATION" | "PERFORMANCE_VIOLATION" | "MEMORY_VIOLATION" | "TIMEOUT_VIOLATION" | "SECURITY_SCAN" | "COMPLIANCE_CHECK" | "DATA_EXPORT" | "INTERNAL_ERROR" | "TENANT_ISOLATION_BREACH" | "VM_ESCAPE_ATTEMPT";
export interface ComplianceReport {
    tenantId: string;
    period: {
        start: number;
        end: number;
    };
    totalExecutions: number;
    successfulExecutions: number;
    failedExecutions: number;
    securityViolations: number;
    performanceViolations: number;
    complianceStatus: "PASSED" | "FAILED" | "WARNING";
    auditTrailHash: string;
    nonRepudiationStatus: boolean;
    exportFormat: "JSON" | "CSV" | "PDF" | "XML";
}
export interface AuditLog {
    events: AuditEvent[];
    metadata: {
        tenantId: string;
        period: {
            start: number;
            end: number;
        };
        totalEvents: number;
        hashAlgorithm: "SHA-256";
        chainOfCustody: true;
    };
    checksum: string;
}
export declare class AuditService extends EventEmitterBase {
    private static instance;
    private events;
    private retentionPeriod;
    private maxEventsPerTenant;
    private enableNonRepudiation;
    private enableComplianceExport;
    private complianceStandards;
    private constructor();
    /**
     * Obtém instância singleton do serviço
     */
    static getInstance(): AuditService;
    /**
     * Registra um evento de auditoria com SHA-256 hashing
     */
    logEvent(event: AuditEvent): void;
    /**
     * Gera hash SHA-256 para registro de auditoria
     */
    private generateChecksum;
    /**
     * Aplica política de retenção (limpeza de eventos antigos)
     */
    private applyRetentionPolicy;
    /**
     * Garante que não exceda limite de eventos por tenant
     */
    private enforceEventLimit;
    /**
     * Limpa eventos antigos do tenant
     */
    private cleanOldEvents;
    /**
     * Registra eventos críticos com informações adicionais
     */
    private logCriticalEvent;
    /**
     * Inicializa política de retenção
     */
    private initializeRetentionPolicy;
    /**
     * Recupera eventos para auditoria específica
     */
    getAuditLog(tenantId: string, startTime?: number, endTime?: number): AuditLog;
    /**
     * Gera hash global SHA-256 para o conjunto de eventos
     */
    private generateGlobalChecksum;
    /**
     * Gera relatório de compliance detalhado
     */
    generateComplianceReport(tenantId: string, period?: {
        start: number;
        end: number;
    }): ComplianceReport;
    /**
     * Exporta dados de compliance em formato específico
     */
    exportComplianceData(tenantId: string, format?: "JSON" | "CSV" | "XML", period?: {
        start: number;
        end: number;
    }): string;
    /**
     * Converte relatório para CSV
     */
    private convertToCSV;
    /**
     * Converte relatório para XML
     */
    private convertToXML;
    /**
     * Cria instância conveniente de evento de auditoria
     */
    createEvent(data: Omit<AuditEvent, "id" | "checksum" | "timestamp">): AuditEvent;
    /**
     * Análise estatística de eventos
     */
    getStatistics(tenantId: string, period?: {
        start: number;
        end: number;
    }): {
        totalEvents: number;
        eventsByType: Record<AuditEventType, number>;
        eventsBySeverity: Record<"low" | "medium" | "high" | "critical", number>;
        eventsByResult: {
            success: number;
            failure: number;
        };
        averageComplianceScore: number;
    };
    /**
     * Valida integridade do audit trail
     */
    validateIntegrity(tenantId: string): {
        isValid: boolean;
        message: string;
        corruptedEventCount: number;
    };
    /**
     * Função de conveniência para eventos de segurança
     */
    logSecurityEvent(executionId: string, tenantId: string, action: string, result: "success" | "failure", details: Record<string, any>): void;
    /**
     * Função de conveniência para eventos de desempenho
     */
    logPerformanceEvent(executionId: string, tenantId: string, timing: number, memory?: number, details?: Record<string, any>): void;
    /**
     * Função de conveniência para eventos de memória
     */
    logMemoryEvent(executionId: string, tenantId: string, memoryUsage: number, targetMemory?: number): void;
    /**
     * Exporta dados de auditoria para backup/restore
     */
    exportAuditData(tenantId: string): string;
    /**
     * Importa dados de auditoria (restauração)
     */
    importAuditData(data: string): void;
    /**
     * Valida dados de auditoria importados
     */
    private validateImportedAudit;
    /**
     * Configurações principais
     */
    configure(options: Partial<{
        retentionDays: number;
        maxEventsPerTenant: number;
        enableNonRepudiation: boolean;
        enableComplianceExport: boolean;
        complianceStandards: string[];
    }>): void;
    /**
     * Limpa todos os eventos de auditoria (uso em testes e manutenção)
     */
    clearAuditLog(tenantId: string): void;
    /**
     * Limpa todos os eventos de todos os tenants (uso com extrema cautela)
     */
    clearAllAuditLogs(): void;
    /**
     * Desabilita logging de auditoria para testes
     */
    disableAuditLogging(): void;
    /**
     * Reabilita logging de auditoria
     */
    enableAuditLogging(): void;
    /**
     * Obtém estatísticas de uso do serviço
     */
    getServiceStats(): {
        totalTenants: number;
        totalEvents: number;
        memoryUsage: number;
        uptime: number;
        lastCleanup: number;
        retentionPolicyActive: boolean;
    };
}
/**
 * Exporta serviço singleton global
 */
export declare const auditService: AuditService;
/**
 * Funções de conveniência para logging rápido
 */
export declare function logRuntimeEvent(executionId: string, tenantId: string, action: string, result: "success" | "failure", details?: Record<string, any>): void;
export declare function logSecurityViolation(executionId: string, tenantId: string, violationType: string, details: Record<string, any>): void;
export declare function logPerformanceViolation(executionId: string, tenantId: string, executionTime: number, memoryUsage: number): void;
export declare function logMemoryViolation(executionId: string, tenantId: string, memoryUsage: number): void;
export declare function generateComplianceReportAsync(tenantId: string, period?: {
    start: number;
    end: number;
}): Promise<ComplianceReport>;
export declare function exportComplianceData(tenantId: string, format?: "JSON" | "CSV" | "XML", period?: {
    start: number;
    end: number;
}): string;
export { AuditService as AuditLogger };
export type { ComplianceReport as AuditReport };
//# sourceMappingURL=audit.d.ts.map