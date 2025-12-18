/**
 * LGPD Compliance Engine v2025
 * Lei Geral de Proteção de Dados Brasileira
 * Enhanced with SHA-256 audit trail integration
 */
import { AuditTrail } from "../audit/auditTrail";
export interface LGPDConfig {
    tenantId: string;
    dataConsent: boolean;
    dataAnonymization: boolean;
    dataRetentionDays: number;
    brazilianDataResidency: boolean;
    rightToDelete: boolean;
    dataOwnerRights: boolean;
    automaticDeletion: boolean;
}
export interface LGPDComplianceResult {
    compliant: boolean;
    violations: string[];
    recommendations: string[];
    anpdRequirements: string[];
}
export declare class LGPDCompliance {
    private auditTrail;
    constructor(auditTrail?: AuditTrail);
    /**
     * Verify LGPD compliance for tenant
     */
    verifyCompliance(config: LGPDConfig): Promise<boolean>;
    /**
     * Check full LGPD compliance with audit trail
     */
    private checkCompliance;
    /**
     * Anonymize personal data LGPD standards
     */
    anonymizeDataLGPD(data: any): any;
    /**
     * Hash sensitive data LGPD compliant
     */
    private hashSensitiveDataLGPD;
    /**
     * Generate LGPD compliance report
     */
    generateLGPDReport(tenantId: string): any;
    /**
     * Calculate LGPD compliance score
     */
    calculateScore(config: LGPDConfig): number;
}
//# sourceMappingURL=lgpdEngine.d.ts.map