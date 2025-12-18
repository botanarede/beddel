"use strict";
/**
 * GDPR Compliance Engine v2025
 * European data protection compliance automático
 * Enhanced with SHA-256 audit trail integration
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.GDPRCompliance = void 0;
const auditTrail_1 = require("../audit/auditTrail");
class GDPRCompliance {
    constructor(auditTrail) {
        this.auditTrail = auditTrail || new auditTrail_1.AuditTrail();
    }
    /**
     * Verify GDPR compliance for tenant
     */
    async verifyCompliance(config) {
        const result = await this.checkCompliance(config);
        return result.compliant;
    }
    /**
     * Check full GDPR compliance with audit trail
     */
    async checkCompliance(config) {
        const violations = [];
        const recommendations = [];
        const operationId = `gdpr-check-${config.tenantId}-${Date.now()}`;
        try {
            // Check data anonymization
            if (!config.dataAnonymization) {
                violations.push("Data anonymization not enabled");
            }
            else {
                recommendations.push("Ensure anonymization algorithms are strong");
            }
            // Check consent management
            if (!config.consentManagement) {
                violations.push("Consent management system not implemented");
            }
            else {
                recommendations.push("Implement granular consent controls");
            }
            // Check right to be forgotten
            if (!config.rightToBeForgotten) {
                violations.push("Right to be forgotten not implemented");
            }
            else {
                recommendations.push("Ensure data deletion within 30 days");
            }
            // Check data portability
            if (!config.dataPortability) {
                violations.push("Data portability not enabled");
            }
            else {
                recommendations.push("Support JSON and XML export formats");
            }
            // Check data retention
            if (config.dataRetentionDays > 2555) {
                // 7 years max
                violations.push("Data retention exceeds GDPR limits");
            }
            else if (config.dataRetentionDays > 730) {
                // 2 years
                recommendations.push("Consider reducing retention period");
            }
            // Log compliance check to audit trail
            const auditHash = await this.auditTrail.logOperation({
                operationId,
                tenantId: config.tenantId,
                operation: "gdpr_compliance_check",
                data: {
                    compliant: violations.length === 0,
                    violationsCount: violations.length,
                    retentionDays: config.dataRetentionDays,
                },
                timestamp: new Date(),
            });
            const compliant = violations.length === 0;
            return {
                compliant,
                violations,
                recommendations,
            };
        }
        catch (error) {
            await this.auditTrail.logOperation({
                operationId,
                tenantId: config.tenantId,
                operation: "gdpr_compliance_error",
                data: {
                    error: error instanceof Error ? error.message : String(error),
                },
                timestamp: new Date(),
                success: false,
            });
            throw error;
        }
    }
    /**
     * Anonymize personal data
     */
    anonymizeData(data) {
        if (typeof data !== "object" || data === null) {
            return data;
        }
        const anonymized = { ...data };
        // Anonymize common personal data fields
        const personalFields = [
            "name",
            "email",
            "phone",
            "cpf",
            "rg",
            "passport",
            "address",
            "birthdate",
            "nationality",
            "photo",
            "signature",
            "voice",
        ];
        for (const field of personalFields) {
            if (anonymized[field]) {
                anonymized[field] = this.hashSensitiveData(anonymized[field]);
            }
        }
        return anonymized;
    }
    /**
     * Hash sensitive data using SHA-256 for GDPR compliance
     */
    hashSensitiveData(data) {
        if (typeof data === "string") {
            // Use SHA-256 hash (simulated for now - in production use crypto.createHash)
            const crypto = require("crypto");
            return crypto.createHash("sha256").update(data).digest("hex");
        }
        return "GDPR_HASH_COMPLEX_" + this.hashSensitiveData(JSON.stringify(data));
    }
    /**
     * Generate data portability export with SHA-256 checksum
     */
    async generateDataExport(tenantId) {
        const exportData = {
            tenantId,
            exportDate: new Date().toISOString(),
            format: "JSON",
            data: {
                profile: "user_data_exported",
                preferences: "export_data_placeholder",
                activities: "user_activities_exported",
            },
            gdprVersion: "2025.1",
        };
        // Generate SHA-256 checksum for data integrity
        const crypto = require("crypto");
        const checksum = crypto
            .createHash("sha256")
            .update(JSON.stringify(exportData))
            .digest("hex");
        const result = {
            ...exportData,
            checksum,
        };
        // Log export operation to audit trail
        const operationId = `gdpr-export-${tenantId}-${Date.now()}`;
        await this.auditTrail.logOperation({
            operationId,
            tenantId,
            operation: "gdpr_data_export",
            data: { checksum, exportDate: result.exportDate },
            timestamp: new Date(),
        });
        return result;
    }
}
exports.GDPRCompliance = GDPRCompliance;
//# sourceMappingURL=gdprEngine.js.map