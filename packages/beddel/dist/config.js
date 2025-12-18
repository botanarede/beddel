"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.auditConfig = exports.performanceTargets = exports.securityProfiles = exports.runtimeConfig = void 0;
exports.runtimeConfig = {
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
exports.securityProfiles = {
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
exports.performanceTargets = [
    { metric: "executionTime", target: 50, unit: "ms", threshold: 75 },
    { metric: "memoryUsage", target: 2, unit: "MB", threshold: 3 },
    { metric: "successRate", target: 99.9, unit: "%", threshold: 99.5 },
    { metric: "isolateCreationTime", target: 100, unit: "ms", threshold: 200 },
    { metric: "poolUtilization", target: 70, unit: "%", threshold: 90 },
];
exports.auditConfig = {
    enabled: true,
    hashAlgorithm: "sha256",
    includeContext: true,
    includeResult: true,
    maxTrailSize: 1024 * 1024 * 100, // 100MB
    retentionPeriod: 90, // 90 dias
};
//# sourceMappingURL=config.js.map