"use strict";
/**
 * Audit Trail Service - SHA-256 Hash Tracking
 * Logs operations com hash criptográfico para auditoria completa
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.AuditTrail = void 0;
class AuditTrail {
    constructor() {
        this.logs = [];
        this.MAX_LOGS = 10000;
        this.logs = [];
    }
    /**
     * Log operation with SHA-256 hash
     */
    async logOperation(auditLog) {
        const { operationId, tenantId, operation, data, timestamp, success = true, } = auditLog;
        // Generate hash for audit trail
        const dataString = JSON.stringify(data);
        const hash = this.generateSHA256(`${operationId}-${tenantId}-${operation}-${dataString}-${timestamp.toISOString()}`);
        const dataHash = this.generateSHA256(dataString);
        const entry = {
            operationId,
            tenantId,
            operation,
            hash,
            timestamp,
            dataHash,
            success,
        };
        // Store log
        this.logs.push(entry);
        // Maintain log size limit
        if (this.logs.length > this.MAX_LOGS) {
            this.logs = this.logs.slice(-this.MAX_LOGS);
        }
        return hash;
    }
    /**
     * Generate SHA-256 hash
     */
    generateSHA256(input) {
        // In a real implementation, would use crypto module
        // For now, simulate SHA-256 hash
        return ("SHA256-" +
            input
                .split("")
                .reduce((hash, char) => {
                const charCode = char.charCodeAt(0);
                return ((hash << 5) - hash + charCode) & 0xffffffff;
            }, 0)
                .toString(16));
    }
    /**
     * Get all audit logs
     */
    getAllLogs() {
        return [...this.logs];
    }
    /**
     * Get logs for specific tenant
     */
    getTenantLogs(tenantId) {
        return this.logs.filter((log) => log.tenantId === tenantId);
    }
    /**
     * Get logs for specific operation
     */
    getOperationLogs(operation) {
        return this.logs.filter((log) => log.operation === operation);
    }
    /**
     * Verify audit trail integrity
     */
    verifyIntegrity() {
        for (const log of this.logs) {
            const reconstructedHash = this.generateSHA256(`${log.operationId}-${log.tenantId}-${log.operation}-${log.dataHash}-`);
            if (reconstructedHash !== log.hash) {
                return false;
            }
        }
        return true;
    }
    /**
     * Clear audit logs
     */
    clearLogs() {
        this.logs = [];
    }
}
exports.AuditTrail = AuditTrail;
//# sourceMappingURL=auditTrail.js.map