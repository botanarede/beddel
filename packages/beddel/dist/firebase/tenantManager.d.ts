/**
 * Multi-Tenant Firebase Manager v2025
 * Isolamento completo de tenants com LGPD/GDPR compliance automático
 */
import * as admin from "firebase-admin";
export interface TenantConfig {
    tenantId: string;
    projectId: string;
    databaseURL: string;
    storageBucket: string;
    securityProfile: "ultra-secure" | "tenant-isolated";
    dataRetentionDays: number;
    lgpdEnabled: boolean;
    gdprEnabled: boolean;
}
export interface TenantIsolationResult {
    success: boolean;
    tenantId: string;
    securityScore: number;
    auditHash: string;
    executionTime: number;
    complianceStatus: {
        lgpd: boolean;
        gdpr: boolean;
    };
}
export declare class MultiTenantFirebaseManager {
    private static instance;
    private tenants;
    private auditTrail;
    private gdprCompliance;
    private lgpdCompliance;
    private constructor();
    static getInstance(): MultiTenantFirebaseManager;
    /**
     * Initialize tenant with complete isolation
     */
    initializeTenant(config: TenantConfig): Promise<TenantIsolationResult>;
    /**
     * Get isolated tenant app with security profile
     */
    getTenantApp(tenantId: string): admin.app.App;
    /**
     * Execute operation in tenant context
     */
    executeInTenant<T>(tenantId: string, operation: string, data: any, callback: () => Promise<T>): Promise<T>;
    /**
     * Configure security rules for tenant
     */
    private configureSecurityRules;
    /**
     * Generate security rules based on profile
     */
    private generateSecurityRules;
    /**
     * Verify LGPD/GDPR compliance for tenant
     */
    private verifyCompliance;
    /**
     * Calculate security score based on configuration
     */
    private calculateSecurityScore;
    /**
     * Validate tenant configuration
     */
    private validateTenantConfig;
    /**
     * Sanitize data for audit trail
     */
    private sanitizeForAudit;
    /**
     * Get all active tenants
     */
    getActiveTenants(): string[];
    /**
     * Get statistics for all tenants
     */
    getTenantStats(): Promise<Map<string, TenantIsolationResult>>;
    /**
     * Safely remove tenant
     */
    removeTenant(tenantId: string): Promise<void>;
}
//# sourceMappingURL=tenantManager.d.ts.map