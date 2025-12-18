/**
 * Audit Trail Service - SHA-256 Hash Tracking
 * Logs operations com hash criptográfico para auditoria completa
 */
export interface AuditLog {
    operationId: string;
    tenantId: string;
    operation: string;
    data: any;
    timestamp: Date;
    success?: boolean;
}
export interface AuditTrailEntry {
    operationId: string;
    tenantId: string;
    operation: string;
    hash: string;
    timestamp: Date;
    dataHash: string;
    success: boolean;
}
export declare class AuditTrail {
    private logs;
    private readonly MAX_LOGS;
    constructor();
    /**
     * Log operation with SHA-256 hash
     */
    logOperation(auditLog: AuditLog): Promise<string>;
    /**
     * Generate SHA-256 hash
     */
    private generateSHA256;
    /**
     * Get all audit logs
     */
    getAllLogs(): AuditTrailEntry[];
    /**
     * Get logs for specific tenant
     */
    getTenantLogs(tenantId: string): AuditTrailEntry[];
    /**
     * Get logs for specific operation
     */
    getOperationLogs(operation: string): AuditTrailEntry[];
    /**
     * Verify audit trail integrity
     */
    verifyIntegrity(): boolean;
    /**
     * Clear audit logs
     */
    clearLogs(): void;
}
//# sourceMappingURL=auditTrail.d.ts.map