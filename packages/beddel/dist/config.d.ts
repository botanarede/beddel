/**
 * Beddel Runtime Configuration - Isolated VM v5
 * Ultra-secure runtime environment with zero-trust architecture
 */
export type AllowedYamlPrimitive = "null" | "boolean" | "integer" | "float" | "string";
export interface YAMLParserConfig {
    schema?: "FAILSAFE_SCHEMA";
    allowedTypes?: AllowedYamlPrimitive[];
    performanceTarget?: number;
    maxDepth?: number;
    maxKeys?: number;
    maxStringLength?: number;
    maxValueSize?: number;
    lazyLoading?: boolean;
    enableCaching?: boolean;
    validateUTF8?: boolean;
    strictMode?: boolean;
    filename?: string;
}
export interface RuntimeConfig {
    memoryLimit: number;
    timeout: number;
    securityScore: number;
    executionTimeTarget: number;
    maxPoolSize: number;
    minPoolSize: number;
    poolIdleTimeout: number;
    defaultSecurityProfile: string;
    allowRestrictedAccess: boolean;
    auditEnabled: boolean;
    auditLevel: "none" | "basic" | "full";
    auditHashAlgorithm: "sha256" | "sha512";
    metricsEnabled: boolean;
    metricsInterval: number;
    maxExecutionHistory: number;
    tenantIsolation: boolean;
    maxConcurrentExecutions: number;
    multiTenant: boolean;
    dataRetention: string;
    auditHash: string;
}
export declare const runtimeConfig: RuntimeConfig;
/**
 * Security profiles for different execution contexts
 */
export interface SecurityProfile {
    name: string;
    memoryLimit: number;
    timeout: number;
    allowExternalAccess: boolean;
    allowedModules: string[];
    restrictedFunctions: string[];
    securityLevel: "low" | "medium" | "high" | "ultra";
}
export declare const securityProfiles: Record<string, SecurityProfile>;
/**
 * Performance targets for monitoring
 */
export interface PerformanceTarget {
    metric: string;
    target: number;
    unit: string;
    threshold: number;
}
export declare const performanceTargets: PerformanceTarget[];
/**
 * Audit trail configuration
 */
export interface AuditConfig {
    enabled: boolean;
    hashAlgorithm: string;
    includeContext: boolean;
    includeResult: boolean;
    maxTrailSize: number;
    retentionPeriod: number;
}
export declare const auditConfig: AuditConfig;
//# sourceMappingURL=config.d.ts.map