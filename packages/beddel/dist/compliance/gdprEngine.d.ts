/**
 * GDPR Compliance Engine v2025
 * European data protection compliance automático
 * Enhanced with SHA-256 audit trail integration
 */
import { AuditTrail } from "../audit/auditTrail";
export interface GDPRConfig {
    tenantId: string;
    dataAnonymization: boolean;
    consentManagement: boolean;
    rightToBeForgotten: boolean;
    dataPortability: boolean;
    dataRetentionDays: number;
}
export interface GDPRComplianceResult {
    compliant: boolean;
    violations: string[];
    recommendations: string[];
}
export declare class GDPRCompliance {
    private auditTrail;
    constructor(auditTrail?: AuditTrail);
    /**
     * Verify GDPR compliance for tenant
     */
    verifyCompliance(config: GDPRConfig): Promise<boolean>;
    /**
     * Check full GDPR compliance with audit trail
     */
    private checkCompliance;
    /**
     * Anonymize personal data
     */
    anonymizeData(data: any): any;
    /**
     * Hash sensitive data using SHA-256 for GDPR compliance
     */
    private hashSensitiveData;
    /**
     * Generate data portability export with SHA-256 checksum
     */
    generateDataExport(tenantId: string): Promise<any>;
}
//# sourceMappingURL=gdprEngine.d.ts.map