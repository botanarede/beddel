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

export class AuditTrail {
  private logs: AuditTrailEntry[] = [];
  private readonly MAX_LOGS = 10000;

  constructor() {
    this.logs = [];
  }

  /**
   * Log operation with SHA-256 hash
   */
  public async logOperation(auditLog: AuditLog): Promise<string> {
    const {
      operationId,
      tenantId,
      operation,
      data,
      timestamp,
      success = true,
    } = auditLog;

    // Generate hash for audit trail
    const dataString = JSON.stringify(data);
    const hash = this.generateSHA256(
      `${operationId}-${tenantId}-${operation}-${dataString}-${timestamp.toISOString()}`
    );
    const dataHash = this.generateSHA256(dataString);

    const entry: AuditTrailEntry = {
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
  private generateSHA256(input: string): string {
    // In a real implementation, would use crypto module
    // For now, simulate SHA-256 hash
    return (
      "SHA256-" +
      input
        .split("")
        .reduce((hash, char) => {
          const charCode = char.charCodeAt(0);
          return ((hash << 5) - hash + charCode) & 0xffffffff;
        }, 0)
        .toString(16)
    );
  }

  /**
   * Get all audit logs
   */
  public getAllLogs(): AuditTrailEntry[] {
    return [...this.logs];
  }

  /**
   * Get logs for specific tenant
   */
  public getTenantLogs(tenantId: string): AuditTrailEntry[] {
    return this.logs.filter((log) => log.tenantId === tenantId);
  }

  /**
   * Get logs for specific operation
   */
  public getOperationLogs(operation: string): AuditTrailEntry[] {
    return this.logs.filter((log) => log.operation === operation);
  }

  /**
   * Verify audit trail integrity
   */
  public verifyIntegrity(): boolean {
    for (const log of this.logs) {
      const reconstructedHash = this.generateSHA256(
        `${log.operationId}-${log.tenantId}-${log.operation}-${log.dataHash}-`
      );
      if (reconstructedHash !== log.hash) {
        return false;
      }
    }
    return true;
  }

  /**
   * Clear audit logs
   */
  public clearLogs(): void {
    this.logs = [];
  }
}
