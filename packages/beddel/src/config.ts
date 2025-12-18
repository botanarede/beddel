/**
 * Beddel Runtime Configuration - Isolated VM v5
 * Ultra-secure runtime environment with zero-trust architecture
 */
export type AllowedYamlPrimitive =
  | "null"
  | "boolean"
  | "integer"
  | "float"
  | "string";

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
  // Memory limits for isolated execution
  memoryLimit: number; // Memory limit in MB per execution
  timeout: number; // Execution timeout in milliseconds
  securityScore: number; // Minimum security score (9.5/10)
  executionTimeTarget: number; // Target execution time in milliseconds

  // Pool configuration
  maxPoolSize: number; // Maximum number of isolates in pool
  minPoolSize: number; // Minimum number of isolates in pool
  poolIdleTimeout: number; // Pool cleanup timeout in ms

  // Security profiles
  defaultSecurityProfile: string; // Default security profile name
  allowRestrictedAccess: boolean; // Allow restricted access to external resources

  // Audit logging
  auditEnabled: boolean; // Enable audit logging
  auditLevel: "none" | "basic" | "full"; // Audit detail level
  auditHashAlgorithm: "sha256" | "sha512"; // Hash algorithm for audit trail

  // Performance monitoring
  metricsEnabled: boolean; // Enable performance metrics
  metricsInterval: number; // Metrics collection interval in ms
  maxExecutionHistory: number; // Maximum number of executions to track

  // Multi-tenant configuration
  tenantIsolation: boolean; // Enable tenant isolation
  maxConcurrentExecutions: number; // Maximum concurrent executions

  // Firebase multi-tenant configuration (2025)
  multiTenant: boolean; // Firebase multi-tenant mode
  dataRetention: string; // LGPD/GDPR data retention policy
  auditHash: string; // Hash algorithm for audit trail
}

export const runtimeConfig: RuntimeConfig = {
  // Core runtime settings
  memoryLimit: 2, // 2MB por execução
  timeout: 5000, // 5 segundos máximo
  securityScore: 9.5, // Target mínimo 9.5/10
  executionTimeTarget: 50, // 50ms target

  // Pool management
  maxPoolSize: 100, // Máximo de 100 isolates
  minPoolSize: 5, // Mínimo de 5 isolates
  poolIdleTimeout: 300000, // 5 minutos idle timeout

  // Security configuration
  defaultSecurityProfile: "ultra-secure",
  allowRestrictedAccess: false, // Sem acesso externo por padrão

  // Audit configuration
  auditEnabled: true,
  auditLevel: "full",
  auditHashAlgorithm: "sha256",

  // Performance monitoring
  metricsEnabled: true,
  metricsInterval: 1000, // Coleta a cada segundo
  maxExecutionHistory: 10000, // Histórico de 10k execuções

  // Multi-tenant settings
  tenantIsolation: true,
  maxConcurrentExecutions: 1000, // Suporte a 1000 execuções simultâneas

  // Firebase multi-tenant configuration (2025)
  multiTenant: true, // Isolamento total de tenants
  dataRetention: "LGPD", // LGPD compliance automatic
  auditHash: "SHA-256", // Hash criptográfico de operações
};

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

export const securityProfiles: Record<string, SecurityProfile> = {
  "ultra-secure": {
    name: "ultra-secure",
    memoryLimit: 2, // 2MB
    timeout: 5000, // 5s
    allowExternalAccess: false,
    allowedModules: [],
    restrictedFunctions: ["require", "eval", "Function", "process"],
    securityLevel: "ultra",
  },
  "high-security": {
    name: "high-security",
    memoryLimit: 4, // 4MB
    timeout: 10000, // 10s
    allowExternalAccess: false,
    allowedModules: ["lodash", "moment"],
    restrictedFunctions: ["eval", "Function"],
    securityLevel: "high",
  },
  "tenant-isolated": {
    name: "tenant-isolated",
    memoryLimit: 8, // 8MB
    timeout: 15000, // 15s
    allowExternalAccess: true,
    allowedModules: ["lodash", "moment", "uuid"],
    restrictedFunctions: ["eval"],
    securityLevel: "medium",
  },
};

/**
 * Performance targets for monitoring
 */
export interface PerformanceTarget {
  metric: string;
  target: number;
  unit: string;
  threshold: number; // Alert threshold
}

export const performanceTargets: PerformanceTarget[] = [
  { metric: "executionTime", target: 50, unit: "ms", threshold: 75 },
  { metric: "memoryUsage", target: 2, unit: "MB", threshold: 3 },
  { metric: "successRate", target: 99.9, unit: "%", threshold: 99.5 },
  { metric: "isolateCreationTime", target: 100, unit: "ms", threshold: 200 },
  { metric: "poolUtilization", target: 70, unit: "%", threshold: 90 },
];

/**
 * Audit trail configuration
 */
export interface AuditConfig {
  enabled: boolean;
  hashAlgorithm: string;
  includeContext: boolean;
  includeResult: boolean;
  maxTrailSize: number;
  retentionPeriod: number; // in days
}

export const auditConfig: AuditConfig = {
  enabled: true,
  hashAlgorithm: "sha256",
  includeContext: true,
  includeResult: true,
  maxTrailSize: 1024 * 1024 * 100, // 100MB
  retentionPeriod: 90, // 90 dias
};
