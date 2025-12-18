/**
 * Beddel - Parser YAML seguro com FAILSAFE_SCHEMA e Runtime Isolado
 *
 * Open source package para parsing YAML com foco máximo em segurança
 * Implementa FAILSAFE_SCHEMA, validações rigorosas, runtime isolado e multi-tenant isolation
 */
export { SecureYamlParser, createSecureYamlParser, parseSecureYaml, } from "./parser/secure-yaml-parser";
export { IsolatedRuntimeManager, runtimeManager, } from "./runtime/isolatedRuntime";
export type { ExecutionOptions, ExecutionResult, RuntimeContext, } from "./runtime/isolatedRuntime";
export { SimpleIsolatedRuntimeManager, runtimeManager as simpleRuntimeManager, IsolatedRuntimeError as SimpleRuntimeError, } from "./runtime/simpleRuntime";
export type { ExecutionOptions as SimpleExecutionOptions, ExecutionResult as SimpleExecutionResult, } from "./runtime/simpleRuntime";
export { DeclarativeAgentInterpreter, declarativeInterpreter, } from "./runtime/declarativeAgentRuntime";
export type { YamlAgentDefinition, YamlAgentInterpreterOptions, YamlExecutionResult, } from "./runtime/declarativeAgentRuntime";
export { DeclarativeSchemaCompiler, DeclarativeSchemaValidationError, SchemaCompilationError, } from "./runtime/schemaCompiler";
export { AgentRegistry, agentRegistry } from "./agents/agentRegistry";
export type { AgentRegistration } from "./agents/agentRegistry";
export { runtimeConfig, securityProfiles, performanceTargets, auditConfig, } from "./config";
export type { RuntimeConfig, SecurityProfile, PerformanceTarget, AuditConfig, } from "./config";
export { YAMLBaseError, YAMLParseError, YAMLSecurityError, YAMLPerformanceError, } from "./errors";
export { SecurityScanner } from "./security/scanner";
export { SecurityScore } from "./security/score";
export { SecurityManager, SecurityMonitor, securityMonitor, SecurityDashboard, securityDashboard, ThreatDetectionEngine, AnomalyDetector, ThreatMLModel, } from "./security";
export type { AlertLevel, SecurityEvent, ThreatAnalysis, DashboardConfig, SecurityMetric, } from "./security";
export { AuditService } from "./runtime/audit";
export { PerformanceMonitor } from "./performance/monitor";
export { default as AutoScaler } from "./performance/autoscaling";
export { MultiTenantFirebaseManager } from "./firebase/tenantManager";
export type { TenantConfig, TenantIsolationResult, } from "./firebase/tenantManager";
export { GDPRCompliance } from "./compliance/gdprEngine";
export { LGPDCompliance } from "./compliance/lgpdEngine";
export type { GDPRConfig, GDPRComplianceResult } from "./compliance/gdprEngine";
export type { LGPDConfig, LGPDComplianceResult } from "./compliance/lgpdEngine";
export { SecureYamlRuntime } from "./integration/secure-yaml-runtime";
export type { ExecutionContext } from "./types/executionContext";
export * as Server from "./server";
//# sourceMappingURL=index.d.ts.map